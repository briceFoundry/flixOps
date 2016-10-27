#!/usr/bin/env python
#------------------------------------------------------------------------------
# pictureInPicture.py - Burns in the latest board version of the panel to the current version's thumbnail
#------------------------------------------------------------------------------
# Copyright (c) 2016 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

import os
import copy
import nuke

from flix.fileServices                import FileService
from flix.fileServices.repathDefault  import RepathDefault
from flix.plugins.recomp              import RenderRecipiesThreader
from flix.core2.shotCutList           import ShotCutList
from flix.utilities.log               import log as log
from flix.rendering                   import FlixNuke

from flix.plugins.pluginDecorator     import PluginDecorator
from flix.core2.mode                  import Mode
from flix.web.serverSession           import ServerSession
from flix.web.flixCore                import FlixCore
from flix.web.serverFlixFunctions     import ServerFlixFunctions

import flix.core2.shotCutList
import flix.remote

# -----------------------------------------------------
# Global Varaibles
# -----------------------------------------------------

serverSession = ServerSession()
fileService = FileService()


class PictureInPicture(PluginDecorator):

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

        self.init(label     ='Picture In Picture',
                  icon      =icon,
                  tooltip   ='Picture In Picture',
                  group     ='Maya',
                  pluginPath='flixConfig.plugins.pictureInPicture.PictureInPicture')

    #--------------------------------------------------------------------------
    # executions
    #--------------------------------------------------------------------------

    def execute(self, shotCutList, selection, additionalData=None):
        setattr(self, 'selection', selection)

        self.shotList = flix.core2.shotCutList.ShotCutList.fromFile(shotCutList.defaultPath())
        self.mode = self.shotList.mode

        # For each selected panel
        for p in self.selection:
            shot = self.shotList[p]
            if shot.isMarker():
                continue
            # Get the path to the layout panel's jpeg (thumbnail)
            layoutPanelJpegPath = self._getPanelFilePath(shot)
            # Find which version is the latest board (i.e. not from Maya)
            latestBoard = self._getLatestStoryVersion(shot)
            if latestBoard is None:
                log("%s has no non-Maya version." % shot)
                continue
            log("latestBoard: %s" % latestBoard)
            # Get the path to the story panel's jpeg (thumbnail)
            latestBoardJpegPath = self._getPanelFilePath(latestBoard)
            # Create nk script using the paths to both jpeg files
            self.renderPip(layoutPanelJpegPath, latestBoardJpegPath, int(self.mode.get('[yResolution]')), int(self.mode.get('[xResolution]')))
            # Refresh the cache and thumbnail in Flix
            self.fileServiceLocal.refreshCache(layoutPanelJpegPath)
            log('__renderCallback:: Reloading image %s' % self.rePath.localize(layoutPanelJpegPath))
            self.serverFlixFunctions.addFeedback("reloadImages", [layoutPanelJpegPath])

    #--------------------------------------------------------------------------
    # methods
    #--------------------------------------------------------------------------
    def _getPanelFilePath(self, shot):
        """ Get the path to the shot's thumbnail jpeg
        """
        kargs = {'beat'   : shot.beat,
                 'setup'   : shot.setup,
                 'version' : shot.version,
                 'frame'   : "%04d" % shot.markInFrame}
        return self.shotList.mode.get('[recipeCompedFile]', kargs)

    def _getLatestStoryVersion(self, shot):
        """ Get the latest story version of a panel (i.e. not coming from Maya)
        """
        for v in self._getRelatedVersions(shot):
            if v["version"] == shot.version:
                continue
            s = flix.core2.shot.Shot(shot.show, shot.sequence, v["beat"], v["setup"], v["version"])
            # Right now we assume if the panel's got a thirdPartyMetaData.json file, it comes from Maya and if not, it comes from story
            if not self.fileServiceLocal.exists(s.recipe.getThirdPartyMetaDataPath()):
                return s
        return None

    def _getRelatedVersions(self, shot):
        """ Get all the related versions for the given panel
        """
        versions = FlixCore().getRelatedVersion(shot)
        versions.reverse()
        return versions

    @flix.remote.autoRemote(flix.remote.kProcGroupNuke)
    def renderPip(self, read1, read2, yRes, xRes):
        """ Create the Nuke script and execute it to render the new thumbnail
        """
        # Clear the nk script
        FlixNuke().clearScript()
        # Tweak this parameter for the pic in pic to be smaller(down to 0) or bigger (up to 1)
        scale = 0.25
        # Create the read nodes for both the layout and board panels
        readNode1 = nuke.createNode("Read", "file {%s}" % self.rePath.localize(read1))
        readNode2 = nuke.createNode("Read", "file {%s}" % self.rePath.localize(read2))
        # Create the transform node to resize and move the board to the bottom right hand corner
        transformNode = nuke.createNode("Transform")
        transformNode.setInput(0, readNode2)
        transformNode["scale"].setValue(scale)
        ytranslate = yRes*(scale-1)/2
        xtranslate = xRes*(1-scale)/2
        transformNode["translate"].setValue([xtranslate, ytranslate])
        # Create the merge node that puts the board over the layout panel
        mergeNode = nuke.createNode("Merge2")
        mergeNode.setInput(1, transformNode)
        mergeNode.setInput(0, readNode1)
        # Create the Write node to render the thumbnail
        writeNode = nuke.createNode("Write")
        writeNode["file"].setValue(self.rePath.localize(read1))
        # Execute the script to render the thumbnail
        nuke.execute(writeNode["name"].getValue(), 1, 1, 1)
        # Comment out to actually save the nk script to troubleshoot or modify
        # nuke.scriptSave(self.rePath.localize(read1.replace(".jpg", ".nk")))
        # Clear the nk script
        FlixNuke().clearScript()
