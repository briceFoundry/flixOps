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
        dialogueFile = self.loadFileBrowser()
        if not dialogueFile or not os.path.exists(dialogueFile) or not dialogueFile[-4:] == ".txt":
            raise flix.exceptions.FlixException("No valid text file selected.")
        self.shotList = flix.core2.shotCutList.ShotCutList.fromFile(shotCutList.defaultPath())
        panels = self.getPanelSetupList()
        with open(dialogueFile) as f:
            dialogueFileContent = f.readlines()
        panelDialogueLines = self.getPanelDialogueLines(panels, dialogueFileContent)
        data = []
        data.append('<Recipies>')
        for panel in self.shotList:
            recipe = panel.recipe
            if not panel.isMarker():
                dialogueLines = panelDialogueLines[recipe.getShortLabelName()]
                if not dialogueLines == [-1]:
                    newDialogue = u""
                    for line in range(dialogueLines[0], dialogueLines[1]+1):
                        newDialogue += dialogueFileContent[line].strip("\t")
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

    def loadFileBrowser(self):
        output = OSUtils.runFileBrowser(kBrowseTypeLoadFiles, 'Select the text file', '/', 'dialogue')
        return escape(output[0].decode('utf-8'))

    def getPanelSetupList(self):
        """ Returns a list of panels with their 'short label name' (e.g. '0010-2' for 'hum_p_0010_v2')
        """
        panelSetupList = []
        for panel in self.shotList:
            panelSetupList.append(panel.recipe.getShortLabelName())
        return panelSetupList

    def getPanelDialogueLines(self, panels, dialogueFileContent):
        """ Returns a dictionary listing the first and last dialogue lines for each panel
        """
        panelDialogueLines = {}
        previousPanel = None
        for panel in panels:
            # Panels with no dialogue get set to -1
            panelDialogueLines[panel] = [-1]
            # Ignore Markers
            if "marker" in panel:
                continue
            panelName = "%s:\n" % panel
            # If this panel has dialogue associated to it in the text file
            if panelName in dialogueFileContent:
                # Record the first line of dialogue for this panel
                panelDialogueLines[panel] = [dialogueFileContent.index(panelName) + 1]
                if previousPanel is not None:
                    # Record the last line of dialogue for the previous panel
                    panelDialogueLines[previousPanel].append(dialogueFileContent.index(panelName) - 2)
                if panel == panels[-1]:
                    panelDialogueLines[panel].append(len(dialogueFileContent)-1)
                else:
                    previousPanel = panel
        log("PANELDIALOGUELINES: %s" % panelDialogueLines)
        return panelDialogueLines




