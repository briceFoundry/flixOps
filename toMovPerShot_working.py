#!/usr/bin/env python
#------------------------------------------------------------------------------
# toMovPerShot.py - Creates a QuickTime for each Flix shot
#------------------------------------------------------------------------------
# Copyright (c) 2014 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

import os
import urllib2, urllib
import copy
import math

from flix.fileServices                import FileService
from flix.fileServices.repathDefault  import RepathDefault
from flix.plugins.toMov               import ToMov
from flix.core2.shotCutList           import ShotCutList
from flix.gui.fileBrowserTypes import kBrowseTypeFolderUsingSaveFile
from flix.utilities.log               import log as log
from flix.utilities.osUtils           import OSUtils
from flix.utilities.editUtils         import EditUtils
import flix.exceptions


from flix.plugins.pluginDecorator     import PluginDecorator
from flix.core2.mode                  import Mode
from flix.web.serverSession           import ServerSession
from flix.core2.markerList           import MarkerList

import flix.core2.shotCutList
import flix.remote
import flix.logger

from xml.sax.saxutils       import escape

# -----------------------------------------------------
# Global Varaibles
# -----------------------------------------------------

serverSession = ServerSession()
fileService = FileService()


class ToMovPerShot(PluginDecorator):

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self):
        self.fileService = flix.fileServices.FileService()
        self.fileServiceLocal = flix.fileServices.fileLocal.FileLocal()
        self.rePath      = RepathDefault()

        self.shotList             = ''

        # load the icon
        iconPath = flix.core2.mode.Mode().get('[FLIX_FOLDER]')+'/assets/20px-quicktime.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label     ='QuickTime per Shot',
                  icon      =icon,
                  tooltip   ='QuickTime per Shot',
                  group     ='Export',
                  pluginPath='flixConfig.plugins.toMovPerShot.ToMovPerShot')

    #--------------------------------------------------------------------------
    # executions
    #--------------------------------------------------------------------------

    def execute(self, shotCutList, selection, additionalData=None):
        self.shotList = flix.core2.shotCutList.ShotCutList.fromFile(shotCutList.defaultPath())
        self.kargs = {'show'    :self.shotList.show,
                 'sequence':self.shotList.sequence,
                 'branch'  :self.shotList.branch,
                 'version' :self.shotList.version}
        self.mode = self.shotList.mode
        self.movDir = self.mode.get("[editorialMOVFolder]")
        movieFile = self.getMovFilePath()
        if movieFile is None:
            raise flix.exceptions.FlixException(msg="Current version does not have an editorial movie.", notify=True)
        else:
            log("Movie File: %s" % movieFile)

        self.addProgress(5)
        output = OSUtils.runFileBrowser(kBrowseTypeFolderUsingSaveFile, 'Choose a folder', '/', 'toMovPerShot')
        self.removeProgress(5)
        # escape output path
        output = escape(output.decode('utf-8'))
        if not output or not os.path.isdir(output):
            raise flix.exceptions.FlixException(error=output, msg='No Valid directory selected.', notify=False)

        shotsInfo = self.getShotsInfo()

        shotMovies = self.toMovPerShot(shotsInfo, movieFile)
        for shotMovie in shotMovies:
            self.fileService.copy(shotMovie, output)

        OSUtils().revealFiles([output])

    #--------------------------------------------------------------------------
    # methods
    #--------------------------------------------------------------------------
    def getMovFilePath(self):
        movieFileName = self.shotList.refVideoFilename
        if movieFileName is not None:
            return "%s/%s" % (self.movDir, movieFileName)

    def getShotsInfo(self):
        markerList = MarkerList.fromShotCutList(self.shotList)
        self.addProgress(len(markerList))
        shotLabels = []
        for marker in markerList:
            shotLabels.append(marker.name)
        markerShotLists = MarkerList.markerShotCutList(self.shotList, markerList)
        if not markerShotLists:
            markerShotLists.append(self.shotList)

        # List of shot info of the form [[shotLabel, firstFrame, lastFrame, dissolveIn, dissolveOut]]
        newShots = []
        firstFrame = 0
        lastFrame = 0
        dialogue = ""
        sequencePanelIndex = 0
        for markerShot in markerShotLists:
            if markerShot.isMarker:
                shotLabel = shotLabels[markerShotLists.index(markerShot)]
                for shot in markerShot:
                    sequencePanelIndex += 1
                    duration = self.shotList[sequencePanelIndex].duration
                    lastFrame += int(round(duration))
                    if shot is markerShot[-1]:
                        dissolveOut = int(round(shot.dissolveOut))
                    if shot is markerShot[0]:
                        dissolveIn = int(round(shot.dissolveIn))
                    newDialogue = str(shot.recipe.getPoses()[0]['dialogue'])
                    if newDialogue != "":
                        dialogue = "\n".join([dialogue, newDialogue])
                newShots.append([shotLabel, firstFrame, lastFrame - 1 + dissolveOut, dissolveIn, dissolveOut, dialogue])
                firstFrame = lastFrame - dissolveOut
                sequencePanelIndex += 1
        log("newShots: %s" % newShots)
        return newShots

    def toMovPerShot(self, shots, movieFile):
        shotMovies = []

        seqName = "%s_v%s_" % (self.shotList.sequence, self.shotList.version)
        for shot in shots:
            # If it's a middle shot, cut the movie in 3 and take the middle part
            segments = str(shot[1]-1) + "," + str(shot[2])
            segment = 1
            if shot is shots[0]:
                # If it's the first shot, cut the movie in 2 and take the 1st part
                segments = str(shot[2]+1)
                segment = 0
            elif shot is shots[-1]:
                # If it's the last shot, cut the movie in 2 and take the 2nd part
                segments = str(shot[1])
            # Get the MOV proc to cut the movie
            self.breakDownMov(movieFile, segments)
            # Rename the randomly named shots with the proper shotlabels and copy them to their respective directories
            toReplace = str(segment).zfill(3) + ".tmp"
            oldName = self.movDir + "/" + toReplace + ".mov"
            shotDir = "%s/%s" % (self.movDir, shot[0])
            self.fileService.createFolders(shotDir)
            newName = oldName.replace(toReplace, "%s/%s%s" % (shot[0], seqName, shot[0]))
            self.fileService.rename(oldName, newName)
            shotMovies.append(newName)
            self.removeProgress(1)
        # Delete unused cut segments
        toDelete = [self.movDir + "/000.tmp.mov", self.movDir + "/002.tmp.mov"]
        for f in toDelete:
            self.fileService.removeFile(f)
        return shotMovies

    @flix.remote.autoRemote(flix.remote.kProcGroupMov, firstProcOnly=True)
    def breakDownMov(self, movieFile, segments):
        ffmpeg = os.environ.get("FLIX_FFMPEG")
        source = self.rePath.localize(movieFile)
        movDir = os.path.abspath(os.path.join(source, os.pardir))
        destination = movDir + "/%03d.tmp.mov"
        ToMov().setLibraryPaths()
        cmd = "%(ffmpeg)s -i %(source)s -f segment -segment_frames %(segments)s -c copy -map 0 -reset_timestamps 1 \"%(destination)s\"" % locals()
        log("ffmpeg cmd: %s" % cmd)
        flix.utilities.osUtils.OSUtils.quickCall(cmd, cwd=os.path.dirname(ffmpeg))
