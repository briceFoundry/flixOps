#!/usr/bin/env python
#------------------------------------------------------------------------------
# importDialogue.py - Imports a Flix text file and assigns dialogue to the panels
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
from flix.gui.fileBrowserTypes        import kBrowseTypeLoadFiles
from flix.utilities.log               import log as log
from flix.utilities.osUtils           import OSUtils
from flix.utilities.editUtils         import EditUtils
import flix.exceptions


from flix.plugins.pluginDecorator     import PluginDecorator
from flix.core2.mode                  import Mode
from flix.web.serverSession           import ServerSession
from flix.core2.markerList            import MarkerList
from flix.web.serverFlixFunctions     import ServerFlixFunctions

import flix.core2.shotCutList
import flix.remote
import flix.logger

from xml.sax.saxutils       import escape
import xml.etree.ElementTree as ET


# -----------------------------------------------------
# Global Variables
# -----------------------------------------------------

serverSession = ServerSession()
fileService = FileService()


class ImportDialogue(PluginDecorator):

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self):
        self.fileService = fileService
        self.rePath      = RepathDefault()

        self.shotList             = ''
        self.serverFlixFunctions = ServerFlixFunctions()

        # load the icon
        iconPath = Mode().get('[FLIX_CONFIG_FOLDER]')+'/plugins/icons/custom_icon.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label     ='Import Dialogue',
                  icon      =icon,
                  tooltip   ='Import dialogue to current edit',
                  group     ='Export',
                  pluginPath='flixConfig.plugins.importDialogue.ImportDialogue')

    #--------------------------------------------------------------------------
    # executions
    #--------------------------------------------------------------------------

    def execute(self, shotCutList, selection, additionalData=None):
        self.shotList = flix.core2.shotCutList.ShotCutList.fromFile(shotCutList.defaultPath())
        newDialogue = "whatever"
        data = []
        data.append('<Recipies>')
        for panel in self.shotList:
            recipe = panel.recipe
            if not panel.isMarker():
                    poses = recipe.getPoses()
                    poseXML = poses[0]['poseXML']
                    poseXML.attrib['dialogue'] = newDialogue
                    recipe.saveRecipeFiles()
                    data.append('<Setup show="%(show)s" sequence="%(sequence)s" beat="%(beat)s" setup="%(setup)s" version="%(version)s">' % recipe.getProperties())
                    data.append(ET.tostring(recipe.getMultiTrackXML()) + "</Setup>")
        data.append("</Recipies>")
        dataString = "".join(data)
        log("DATASTRING: %s" % dataString)
        self.serverFlixFunctions.addFeedback('reloadSetupsMultiTracks', dataString)





