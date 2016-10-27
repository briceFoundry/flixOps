#!/usr/bin/env python
#------------------------------------------------------------------------------
# logMultipleShotEdits.py - Logs latest shotEdits from every sequence in the current show
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
import xml.etree.ElementTree as ET


# -----------------------------------------------------
# Global Varaibles
# -----------------------------------------------------

serverSession = ServerSession()
fileService = FileService()


class LogMultipleShotEdits(PluginDecorator):

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

        self.init(label     ='Log Multiple Shot Edits',
                  icon      =icon,
                  tooltip   ='Logs latest shotedit from every sequence',
                  group     ='Export',
                  pluginPath='flixConfig.plugins.logMultipleShotEdits.LogMultipleShotEdits')

    #--------------------------------------------------------------------------
    # executions
    #--------------------------------------------------------------------------

    def execute(self, shotCutList, selection, additionalData=None):
        self.shotList = flix.core2.shotCutList.ShotCutList.fromFile(shotCutList.defaultPath())
        self.show = self.shotList.show
        sequences = flix.core.sequence.Sequence.sequencesToXMLList(flix.core.sequence.Sequence.getSequences(self.show))
        for seq in sequences:
            seqName = seq.attrib["name"]
            latestShotEdit = self.getLatestShotCutList(seqName)
            log("latestShotEdit: %s" % latestShotEdit)

    def getLatestSequenceVersion(self, sequence, branch="main"):
        maxEditVersions = flix.versioning.flixVersioning.FlixVersioning().getCurrentFlixEditVersion(self.show, sequence, branch)
        i = 0

        sequenceObj = flix.core.sequence.Sequence(self.show, sequence)
        for i in range(maxEditVersions, -1, -1):
            editVersion = str(i)
            editorialPath = sequenceObj.getShotEditPath(branch, editVersion)

            if self.fileService.exists(editorialPath):
                break
        return i

    def getLatestShotCutList(self, sequence, branch="main"):
        editVersion = self.getLatestSequenceVersion(sequence)
        sequenceObj = flix.core.sequence.Sequence(self.show, sequence)
        editorialPath = sequenceObj.getShotEditPath(branch, editVersion)

        if not fileService.exists(editorialPath):
            flix.logger.log('Could not get the latest shotcutlist %s' % self.rePath.localize(editorialPath), isError=True)
            return None

        return flix.core2.shotCutList.ShotCutList.fromFile(editorialPath)


