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

from flixConfig.plugins.shotInfo import ShotInfo

# -----------------------------------------------------
# Global Varaibles
# -----------------------------------------------------

serverSession = ServerSession()
fileService = FileService()


class ToMovPerShot(PluginDecorator):

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self, shotCutList=''):
        self.fileService = flix.fileServices.FileService()
        self.fileServiceLocal = flix.fileServices.fileLocal.FileLocal()
        self.rePath      = RepathDefault()
        # self.shotList    = shotCutList
        if shotCutList != '':
            self.shotList = flix.core2.shotCutList.ShotCutList.fromFile(shotCutList.defaultPath())
            self.kargs = {'show'    :self.shotList.show,
                     'sequence':self.shotList.sequence,
                     'branch'  :self.shotList.branch,
                     'version' :self.shotList.version}
            self.mode = self.shotList.mode
            self.movDir = self.mode.get("[editorialMOVFolder]")

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
        movieFileName = self.shotList.refVideoFilename
        if movieFileName is None:
            raise flix.exceptions.FlixException(msg="Current version does not have an editorial movie.", notify=True)
        else:
            movieFile = "%s/%s" % (self.movDir, movieFileName)
            log("Movie File: %s" % movieFile)

        self.addProgress(5)
        output = OSUtils.runFileBrowser(kBrowseTypeFolderUsingSaveFile, 'Choose a folder', '/', 'toMovPerShot')
        self.removeProgress(5)
        # escape output path
        output = escape(output.decode('utf-8'))
        if not output or not os.path.isdir(output):
            raise flix.exceptions.FlixException(error=output, msg='No Valid directory selected.', notify=False)

        shotInfoObject = ShotInfo(self.shotList)
        shots = shotInfoObject.getShotsInfo()
        self.addProgress(len(shots))

        shotMovies = self.toMovPerShot(shots, movieFile)
        for shotMovie in shotMovies:
            self.fileService.copy(shotMovie, output)

        OSUtils().revealFiles([output])

    #--------------------------------------------------------------------------
    # methods
    #--------------------------------------------------------------------------
    def toMovPerShot(self, shots, movieFile):
        shotMovies = []

        seqName = "%s_v%s_" % (self.shotList.sequence, self.shotList.version)
        for shot in shots:
            # If it's a middle shot, cut the movie in 3 and take the middle part
            segments = str(shot['first frame'] - 1) + "," + str(shot['last frame'])
            segment = 1
            if shot is shots[0]:
                # If it's the first shot, cut the movie in 2 and take the 1st part
                segments = str(shot['last frame'])
                segment = 0
            # Get the MOV proc to cut the movie
            self.breakDownMov(movieFile, segments)
            # Rename the randomly named shots with the proper shotlabels and copy them to their respective directories
            toReplace = str(segment).zfill(3) + ".tmp"
            oldName = self.movDir + "/" + toReplace + ".mov"
            shotDir = "%s/%s" % (self.movDir, shot['shot label'])
            self.fileService.createFolders(shotDir)
            newName = oldName.replace(toReplace, "%s/%s%s" % (shot['shot label'], seqName, shot['shot label']))
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
        # ToMov().setLibraryPaths()
        self.setLibraryPaths()
        cmd = "%(ffmpeg)s -i %(source)s -f segment -segment_frames %(segments)s -c copy -map 0 -reset_timestamps 1 \"%(destination)s\"" % locals()
        log("ffmpeg cmd: %s" % cmd)
        flix.utilities.osUtils.OSUtils.quickCall(cmd, cwd=os.path.dirname(ffmpeg))

    def setLibraryPaths(self):
        ffmpegFolder = os.path.dirname(os.environ.get('FLIX_FFMPEG'))
        ffmpegLibs = "/".join([ffmpegFolder, "lib"])
        lameLibs = flix.thirdParty.getLameLibPath()
        if ffmpegLibs not in os.environ.get('LD_LIBRARY_PATH'):
            os.environ["LD_LIBRARY_PATH"] = ":".join([ffmpegLibs, os.environ.get('LD_LIBRARY_PATH')])
        if lameLibs not in os.environ.get('LD_LIBRARY_PATH'):
            os.environ["LD_LIBRARY_PATH"] = ":".join([lameLibs, os.environ.get('LD_LIBRARY_PATH')])



