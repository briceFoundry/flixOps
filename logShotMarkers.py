#!/usr/bin/env python
#------------------------------------------------------------------------------
# logShotMarkers.py - Creates a QuickTime for each Flix shot
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


class LogShotMarkers(PluginDecorator):

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self):
        self.fileService = fileService
        self.rePath      = RepathDefault()

        self.shotList             = ''

        # load the icon
        iconPath = Mode().get('[FLIX_CONFIG_FOLDER]')+'/plugins/icons/custom_icon.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label     ='Log Shot Markers',
                  icon      =icon,
                  tooltip   ='Logs what shots, markers and markerlists are',
                  group     ='Export',
                  pluginPath='flixConfig.plugins.logShotMarkers.LogShotMarkers')

    #--------------------------------------------------------------------------
    # executions
    #--------------------------------------------------------------------------

    def execute(self, shotCutList, selection, additionalData=None):
        self.shotList = flix.core2.shotCutList.ShotCutList.fromFile(shotCutList.defaultPath())
        log("shotList: %s" % self.shotList)
        self.kargs = {'show'    :self.shotList.show,
                 'sequence':self.shotList.sequence,
                 'branch'  :self.shotList.branch,
                 'version' :self.shotList.version}
        self.mode = self.shotList.mode

        markerList = MarkerList.fromShotCutList(self.shotList)
        log("markerList: %s" % markerList)
        for marker in markerList:
            log("marker: %s" % marker)
        markerShotLists = MarkerList.markerShotCutList(self.shotList, markerList)
        log("markerShotLists 1: %s" % markerShotLists)
        if not markerShotLists:
            markerShotLists.append(self.shotList)
            log("markerShotLists was False, new one: %s" % markerShotLists)

        for markerShot in markerShotLists:
            log("markerShot: %s" % markerShot)
            if markerShot.isMarker:
                for shot in markerShot:
                    log("shot: %s" % shot)
