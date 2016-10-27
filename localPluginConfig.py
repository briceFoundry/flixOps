#------------------------------------------------------------------------------
# localPluginConfig.py - defines global flix plugins
#------------------------------------------------------------------------------
# Copyright (c) 2014 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

from flix.plugins.pluginConfig import PluginConfig
from flix.plugins.toShotgun    import ToShotgun
from flix.utilities.log        import log as log

# Custom plugins
try:
    from flixConfig.plugins.toPDFSelection       import ToPDFSelection
    from flixConfig.plugins.toPDFShots           import ToPDFShots
    from flixConfig.plugins.toMovDialogue        import ToMovDialogue
    from flixConfig.plugins.toMovPerShot         import ToMovPerShot
    from flixConfig.plugins.photoshopEachFile    import PhotoshopEachFile
    from flixConfig.plugins.pictureInPicture     import PictureInPicture
    from flixConfig.plugins.toShotgunGEAH        import ToShotgunGEAH
    from flixConfig.plugins.renameMarkers        import RenameMarkers
    from flixConfig.plugins.logShotMarkers       import LogShotMarkers
    from flixConfig.plugins.logMultipleShotEdits import LogMultipleShotEdits
    from flixConfig.plugins.nukeTestEA           import NukeTestEA
    from flixConfig.plugins.importDialogue       import ImportDialogue
    from flixConfig.plugins.shotsToCSV           import ShotsToCSV
    from flixConfig.plugins.toAvidCopy           import ToAvidCopy
except Exception, e:
    log("Failed to import a custom plugin: %s" % e, isError=True)


class LocalPluginConfig(PluginConfig):

    def __init__(self):
        """Initialize the plugins that will show up in Flix gui"""
        super(LocalPluginConfig, self).__init__()
        try:
            # Edit plugins
            PhotoshopEachFile().default()
            # Maya plugins
            PictureInPicture()
            # PDF plugins
            ToPDFSelection()
            ToPDFShots()
            # Export plugins
            ToMovDialogue()
            ToMovPerShot()
            ToShotgunGEAH()
            RenameMarkers()
            LogShotMarkers()
            LogMultipleShotEdits()
            NukeTestEA()
            # Import plugins
            ImportDialogue()
            ShotsToCSV()
            ToAvidCopy()
        except Exception, e:
            log("Failed to initialize a custom plugin: %s" % e, isError=True)
        # ToShotgun().disable()
