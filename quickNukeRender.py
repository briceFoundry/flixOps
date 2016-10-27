#!/usr/bin/env python
#------------------------------------------------------------------------------
# toMovPerShot.py - Creates a QuickTime for each Flix shot
#------------------------------------------------------------------------------
# Copyright (c) 2014 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

import os

from flix.fileServices                import FileService
from flix.fileServices.repathDefault  import RepathDefault
from flix.utilities.log               import log as log
from flix.utilities.osUtils           import OSUtils
from flix.utilities.editUtils         import EditUtils
import flix.exceptions


from flix.plugins.pluginDecorator     import PluginDecorator
from flix.core2.mode                  import Mode
from flix.web.serverSession           import ServerSession

import flix.core2.shotCutList
import flix.remote
import flix.logger

import nuke

# -----------------------------------------------------
# Global Varaibles
# -----------------------------------------------------

serverSession = ServerSession()
fileService = FileService()

_flixNuke = None
def FlixNuke():
    global _flixNuke
    if _flixNuke is None:
        config = os.environ['FLIX_NUKE']
        configClass = config.split('.')[-1]
        configModule = '.'.join(config.split('.')[0:-1])
        tmp = __import__(configModule, globals(), locals(), [configClass], -1)
        _flixNuke = getattr(tmp, configClass)()
    return _flixNuke


class QuickNukeRender(PluginDecorator):

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self):
        self.fileService = fileService
        self.rePath      = RepathDefault()
        self.flixNuke = FlixNuke()

        self.shotList             = ''

        # load the icon
        iconPath = Mode().get('[FLIX_FOLDER]')+'/assets/custom_icon.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label     ='Quick Nuke Render',
                  icon      =icon,
                  tooltip   ='Quick Nuke Render',
                  group     ='Export',
                  pluginPath='flixConfig.plugins.quickNukeRender.QuickNukeRender')

    #--------------------------------------------------------------------------
    # executions
    #--------------------------------------------------------------------------

    def execute(self, shotCutList, selection, additionalData=None):
        # nukeFile = "/Users/brice/Desktop/testNuke/testNukeScript.nk"
        # frameRange = "1-5"
        # fileOutNode = "fileOut_master"
        # FlixNuke().basicRenderScript(nukeFile, frameRange, fileOutNode)
        nukeFile = "/Users/brice/Desktop/testNuke/test2.nk"
        fileOutNode = "fileOut_master"
        self.createScript(nukeFile, fileOutNode)
        self.flixNuke.basicRenderScript(nukeFile, "1-5", fileOutNode)

    @flix.remote.autoRemote(flix.remote.kProcGroupNuke)
    def createScript(self, nukeFile, fileOutNode):
        FlixNuke().clearScript()

        cbNode = nuke.createNode("CheckerBoard2")
        writeNode = nuke.createNode("Write")
        writeNode["name"].setValue(fileOutNode)
        writeNode["file"].setValue("/Users/brice/Desktop/testNuke/test.####.jpeg")
        writeNode.setInput(0, cbNode)
        nuke.scriptSave(nukeFile)






