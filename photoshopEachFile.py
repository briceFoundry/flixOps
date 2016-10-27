#------------------------------------------------------------------------------
# photoshopEachFile.py -
#------------------------------------------------------------------------------
# Copyright (c) 2016 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

import time

import flix
from flix import fileServices


class PhotoshopEachFile(flix.plugins.pluginDecorator.PluginDecorator):
    def __init__(self):
        self.name = 'PhotoshopEachFile'
        self.fileService = fileServices.FileService()
        self.fileServiceLocal = fileServices.fileLocal.FileLocal()
        self.repath = fileServices.Repath()

        iconPath = flix.core2.mode.Mode().get('[FLIX_FOLDER]')+'/assets/20px-photoshop.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label='Photoshop (Each File)',
                  icon=icon,
                  tooltip='Edit selected panels in Photoshop (using different documents for each panel)',
                  group='Drawing',
                  pluginPath='flixConfig.plugins.photoshopEachFile.PhotoshopEachFile',
                  saveFirst=False,
                  completeMessage="")

    def execute(self, shotList, selection, additionalData=None):
        psPlugin = flix.plugins.photoshop.Photoshop()
        for index in selection:
            psPlugin.execute(shotList, [index])
            time.sleep(1)
