#------------------------------------------------------------------------------
# batchMarkerRename.py -
#------------------------------------------------------------------------------
# Copyright (c) 2014 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

from flix.fileServices                import FileService
from flix.fileServices.repathDefault  import RepathDefault
import flix.core2.shot
from flix.core2.shotCutList           import ShotCutList
from flix.core2.mode                  import Mode
from flix.utilities.log               import log as log

from flix.plugins.pluginDecorator     import PluginDecorator
from flix.web.serverSession           import ServerSession
from flix.web.serverFlixFunctions     import ServerFlixFunctions

import flix.core2.shotCutList
import xml.etree.ElementTree as ET

# -----------------------------------------------------
# Global Varaibles
# -----------------------------------------------------

serverSession = ServerSession()
fileService = FileService()

kMarkerNameRegex = '[markerNameRegex]'
kMarkerNameIncrement = '[markerNameIncrement]'

class RenameMarkers(PluginDecorator):

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self):
        self.fileService = fileService
        self.rePath      = RepathDefault()
        self.fileServiceLocal = flix.fileServices.fileLocal.FileLocal()
        self.serverFlixFunctions = ServerFlixFunctions()

        self.shotList             = ''

        # load the icon
        iconPath = Mode().get('[FLIX_CONFIG_FOLDER]')+'/plugins/icons/custom_icon.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label     ='Rename Markers',
                  icon      =icon,
                  tooltip   ='Rename Markers',
                  group     ='Export',
                  pluginPath='flixConfig.plugins.renameMarkers.RenameMarkers')

    def execute(self, shotCutList, selection, additionalData=None):
        self.shotList = flix.core2.shotCutList.ShotCutList.fromFile(shotCutList.defaultPath())
        self.mode = self.shotList.mode

        shotNumber = int(self.mode.get(kMarkerNameIncrement))
        data = []
        data.append('<Recipies>')
        for shot in self.shotList:
            if shot.isMarker():
                recipe = shot.recipe
                properties = recipe.getProperties()
                newName = self.mode.get(kMarkerNameRegex) % shotNumber
                poses = recipe.getPoses()
                poseXML = poses[0]['poseXML']
                poseXML.attrib['dialogue'] = newName
                recipe.saveRecipeFiles()
                data.append('<Setup show="%(show)s" sequence="%(sequence)s" beat="%(beat)s" setup="%(setup)s" version="%(version)s">' % recipe.getProperties())
                data.append(ET.tostring(recipe.getMultiTrackXML()) + "</Setup>")
                shotNumber += int(self.mode.get(kMarkerNameIncrement))
        data.append("</Recipies>")
        dataString = "".join(data)
        log("DATASTRING: %s" % dataString)
        self.serverFlixFunctions.addFeedback('reloadSetupsMultiTracks', dataString)


