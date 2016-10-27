#------------------------------------------------------------------------------
# shotsToCSV.py
#------------------------------------------------------------------------------
# Copyright (c) 2015 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

from flix                   import fileServices
import flix.exceptions
from flix.utilities.osUtils import OSUtils
from flix.utilities.log     import log as log
from xml.sax.saxutils       import escape
from flix.plugins           import pluginDecorator
from flix.plugins.toCSV     import ToCSV
from flix.core2.markerList import MarkerList
from flix.gui.fileBrowserTypes import kBrowseTypeFolderUsingSaveFile
from collections  import OrderedDict
from xml.sax.saxutils import unescape

import flix
import flix.core2.mode
import flix.fileServices.repathDefault
import os
import urllib
import csv
import flix.utilities.commonUtils as utils

from flixConfig.plugins.shotInfo import ShotInfo


#------------------------------------------------------------------------------
# class
#------------------------------------------------------------------------------

class ShotsToCSV(ToCSV):

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self, shotCutList=''):
        self.fileService = fileServices.FileService()
        self.fileServiceLocal = flix.fileServices.fileLocal.FileLocal()
        self.serverSession = flix.web.serverSession.ServerSession()
        self.repath = flix.fileServices.repathDefault.RepathDefault()
        self.selection = None
        self.shotCutList  = shotCutList
        self.panelList = []
        self.mode      = None
        self.kargs     = OrderedDict()

        # load the icon
        iconPath = flix.core2.mode.Mode().get('[FLIX_FOLDER]')+'/assets/20px-exportCSV.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label='Export Shots to CSV',
                  icon=icon,
                  tooltip='Export Shots Data to CSV',
                  group='Export',
                  pluginPath='flixConfig.plugins.shotsToCSV.ShotsToCSV')


    def execute(self, shotCutList, selection, additionalData=None, output=False):
        """ Copy panels into user defined directory
        """
        self.shotCutList  = shotCutList.loadAll()

        if not self.shotCutList:
            raise flix.exceptions.FlixException("CSV can not be created for empty sequence",
                                                error=ValueError("No values in ShotCutList"),
                                                notify=True)

        self.selection = selection
        self._dialogueErrors = []

        self.setKargs()
        # collect panel and shot infomation.
        self.getSequenceInfo()
        self.shots = ShotInfo(self.shotCutList).getShotsInfo()

        if not output:
            output = OSUtils.runFileBrowser(kBrowseTypeFolderUsingSaveFile, 'Choose a folder', '/', 'toCSV')
            # escape output path
            output = escape(output.decode('utf-8'))
            if not output or not os.path.isdir(output):
                raise flix.exceptions.FlixException(error="Directory error", msg='No Valid directory selected.')

        fileName = '{Sequence Folder}_v{Version}.csv'.format(**self.kargs)
        fileOut  = '/'.join([output, fileName])

        # tell the user what sequence and sequence version is exporting and where.
        log('Exporting out sequence csv: %s into: %s' % (fileName, output), isInfo=True)
        # # if outputPath exists and all panels exist export the sequence.
        if os.path.exists(output):
            self.saveCSV(fileOut)
            OSUtils().revealFiles([fileOut])
        if self._dialogueErrors:
            failedDialogues = ", ".join([shot.recipe.getLabelName() for shot in self._dialogueErrors])
            self._execMessage = "Executed %s Plugin Successfully\n\nFailed to parse dialogue for the following clips:\n%s"%(self.label, failedDialogues)


    #--------------------------------------------------------------------------
    # methods
    #--------------------------------------------------------------------------

    def saveCSV(self, fileOut):
        with open(fileOut, 'wb') as csvFile:
            csvFile.write(u'\ufeff'.encode('utf8'))
            csvFile.truncate()
            writer = csv.DictWriter(csvFile, fieldnames=['Attribute', 'Value'])
            writer.writeheader()
            for k, v in self.kargs.iteritems():
                writer.writerow({'Attribute': k, 'Value' : unicode(v).encode('utf8')})
            writer.writerow({'Attribute': '', 'Value': ''})
            writer.writerow({'Attribute': '', 'Value': ''})
            writer.writerow({'Attribute': 'Shots', 'Value': '--------'})
            writer = csv.DictWriter(csvFile, fieldnames=self.shots[0].keys())
            writer.writeheader()
            for shot in self.shots:
                writer.writerow({k:unescape(unicode(v).encode('utf8')) for k,v in shot.items()})
