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
import nuke

from flix.fileServices                import FileService
from flix.fileServices.repathDefault  import RepathDefault
from flix.plugins.toMov               import ToMov
from flix.core2.shotCutList           import ShotCutList
from flix.gui.fileBrowserTypes import kBrowseTypeFolderUsingSaveFile
from flix.utilities.log               import log as log
from flix.utilities.osUtils           import OSUtils
from flix.utilities.editUtils         import EditUtils
from flix.rendering                   import FlixNuke
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


class BurnInPerShot(PluginDecorator):

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self):
        self.fileService = fileService
        self.rePath      = RepathDefault()

        self.shotList             = ''

        # load the icon
        iconPath = Mode().get('[FLIX_FOLDER]')+'/assets/custom_icon.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label     ='BurnIn per Shot',
                  icon      =icon,
                  tooltip   ='BurnIn per Shot',
                  group     ='Export',
                  pluginPath='flixConfig.plugins.burnInPerShot.BurnInPerShot')

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
        movieFile = self.rePath.localize(self.__getMovFilePath())
        if movieFile is None:
            raise flix.exceptions.FlixException(msg="Current version does not have an editorial movie.", notify=True)
        else:
            log("Movie File: %s" % movieFile)

        self.addProgress(5)
        output = OSUtils.runFileBrowser(kBrowseTypeFolderUsingSaveFile, 'Choose a folder', '/', 'burnInPerShot')
        self.removeProgress(5)
        # escape output path
        output = escape(output.decode('utf-8'))
        if not output or not os.path.isdir(output):
            raise flix.exceptions.FlixException(error=output, msg='No Valid directory selected.', notify=False)

        # markerShotLists = self.getMarkerList(self.shotList)

        markerList = MarkerList.fromShotCutList(self.shotList)
        self.addProgress(len(markerList))
        shotLabels = []
        for marker in markerList:
            shotLabels.append(marker.name)
        markerShotLists = MarkerList.markerShotCutList(self.shotList, markerList)
        if not markerShotLists:
            markerShotLists.append(self.shotList)

        self.markIn = 1
        self.markOut = 0
        markerTuples = []
        for markerShot in markerShotLists:
            if markerShot.isMarker:
                for shot in markerShot:
                    self.markOut += int(round(shot.duration))
                markerTuples.append((self.markIn, self.markOut))
                self.markIn = self.markOut + 1

        self.breakDownMov(movieFile, markerTuples, shotLabels, self.movDir)

        for shot in shotLabels:
            toReplace = str(shotLabels.index(shot)).zfill(3) + ".tmp"
            oldName = self.movDir + "/" + toReplace + ".mov"
            newName = oldName.replace(toReplace, shot + "_v" + str(self.shotList.version))
            try:
                # self.fileService.rename(oldName, newName)
                self.addBurnIns(oldName, newName)
                self.fileService.copy(newName, output)
                self.fileService.removeFile(oldName)
                self.fileService.removeFile(newName)
            except Exception, e:
                log("Failed to rename, copy or remove the temp mov: %s" % e, isError=True)
            self.removeProgress(1)

        # self.removeProgress()
        OSUtils().revealFiles([output])

    #--------------------------------------------------------------------------
    # methods
    #--------------------------------------------------------------------------
    def __getMovFilePath(self):
        movieFileName = self.shotList.refVideoFilename
        if movieFileName is not None:
            return "%s/%s" % (self.movDir, movieFileName)

    @flix.remote.autoRemote(flix.remote.kProcGroupMov)
    def breakDownMov(self, source, markerTuples, shotLabels, outputDir):
        ffmpeg = os.environ.get("FLIX_FFMPEG")
        destination = self.rePath.localize(outputDir) + "/%03d.tmp.mov"
        segments = ""
        for markerTuple in markerTuples:
            segments = segments + str(markerTuple[1]) + ","
        segments = segments[:-1]
        cmd = "%s -i %s -f segment -segment_frames %s -c copy -map 0 -reset_timestamps 1 \"%s\"" % (ffmpeg, source, segments, destination)
        flix.utilities.osUtils.OSUtils.quickCall(cmd, cwd=os.path.dirname(ffmpeg))

    @flix.remote.autoRemote(flix.remote.kProcGroupNuke)
    def addBurnIns(self, oldMovPath, newMovPath):
        FlixNuke().clearScript()

        readNode = nuke.createNode("Read", "file {%s}" % self.rePath.localize(oldMovPath))
        firstframe = int(readNode["origfirst"].getValue())
        lastframe = int(readNode["origlast"].getValue())

        textNode = nuke.createNode("Text2")
        textNode.setInput(0, readNode)
        textNode["color"].setValue(0)
        textNode["message"].setValue("Hello World!")
        textNode["xjustify"].setValue("left")
        textNode["yjustify"].setValue("bottom")
        writeNode = nuke.createNode("Write")
        writeNode["file"].setValue(self.rePath.localize(newMovPath))
        writeNode.setInput(0, textNode)

        nuke.execute(writeNode["name"].getValue(), firstframe, lastframe, 1)
        nuke.scriptSave(self.rePath.localize(newMovPath.replace(".mov", ".nk")))

