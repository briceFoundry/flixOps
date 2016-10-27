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
from flix.plugins.avid      import Avid
from flix.core2.markerList  import MarkerList
from xml.sax.saxutils       import escape, unescape
from flix.web.flixCore      import FlixCore

import flix
import flix.core2.mode
import flix.fileServices.repathDefault
import os
import urllib
import flix.utilities.commonUtils as utils

from flixConfig.plugins.shotInfo import ShotInfo

from flix.core2.mode import Mode
from flix.editorial import AvidWorkflow
from flix.core.sequence import Sequence

# import flix.toEditorial
# import flix.remote
# import flix.utilities.template
# import flix.plugins.toPDF

# import os
# import itertools
# import urllib
# import flix
# from flix.plugins import pluginDecorator
# from flix.utilities.log import log
# from flix.core2.mode import Mode
# from flix.editorial import AvidWorkflow
# from flix.core.sequence import Sequence
# import flix.fileServices.fileLocal
# import flix.core2.shotCutList
# import flix.core2.shot
# import flix.toEditorial
# import flix.remote
# import flix.utilities.template
# from xml.sax.saxutils import escape
# import flix.plugins.toPDF


kParamPublishTemplate = '[fcpSummaryTemplate]'
kParamShotCutListFile = '[editorialFLEFile]'
# kAAFDestinationFolder = '[AAFDestinationFolder]'

#------------------------------------------------------------------------------
# class
#------------------------------------------------------------------------------

class ToAvidCopy(Avid):

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self):
        self.fileService = flix.fileServices.FileService()
        self.fileServiceLocal = flix.fileServices.fileLocal.FileLocal()
        self.repath = flix.fileServices.Repath()

        # load the icon
        iconPath = flix.core2.mode.Mode().get('[FLIX_FOLDER]') + '/assets/40px-avid.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label='Avid Copy',
                  icon=icon,
                  tooltip='Publish edit to avid and copy AAFs',
                  group='Editorial',
                  pluginPath='flixConfig.plugins.toAvidCopy.ToAvidCopy',
                  saveFirst=True,
                  completeMessage="\nExecuted Avid Plugin Successfully\nRefer to e-mail for more info.\n")


    def execute(self, shotCutList, selection, additionalData=None):
        if not additionalData is None:
            referenceCutList = additionalData.get('reference', None)
            comment = additionalData.get('comment', "")

        show      = shotCutList.show
        sequence  = shotCutList.sequence
        version   = shotCutList.version
        branch    = shotCutList.branch
        mode      = Mode(show, sequence)

        log("To Avid: Publishing: %s %s %s %s Comment: %s" % (show, sequence, branch, version, comment), isInfo=True)

        # get path to cutlist to publish
        shotCutListPath = flix.core2.shotCutList.ShotCutList.getDefaultPath( \
            mode, version, branch)

        # check if reference cutlist is required
        referenceCutListPath = None
        referenceVersion = -2
        if referenceCutList is not None:
            referenceVersion     = referenceCutList.version
        if referenceVersion == -2:
            referenceCutListPath = self.getMostRecentPublishedEdit( \
                show, sequence, version, branch)
        elif referenceVersion > 0:
            referenceCutList.load()
            referenceCutListPath = flix.core2.shotCutList.ShotCutList.getDefaultPath( \
                mode, referenceVersion, branch)

        # publish the cutlist
        avidWorkflow = AvidWorkflow()
        result = avidWorkflow.publish(shotCutListPath,
                                      referenceCutListPath,
                                      comment)

        if referenceCutList is None:
            referenceCutList = shotCutList

        self.__shotCutList      = shotCutList
        self.__shotCutList.load()
        self.__referenceCutList = referenceCutList
        self.__newShots         = avidWorkflow.newShots
        self.__errors           = avidWorkflow.errors
        self.__encodingTime     = avidWorkflow.encodingTime
        self.__comment          = comment
        self._dialogueErrors    = avidWorkflow.dialogueErrors

        self.saveAle(shotCutList)

        # email publish summary
        self.emailSummary()
        self.flixCore = FlixCore()
        importMedia = self.flixCore.examineFLEForNewAAFs(show, sequence, version, branch)
        log("importMedia: %s" % importMedia)
        destinationFolder = shotCutList.mode.get('[AAFDestinationFolder]')
        log("destinationFolder: %s" % destinationFolder)
        if self.fileService.exists(destinationFolder):
            self.flixCore.importAAFs(show, sequence, version, branch, destinationFolder)
        else:
            # self.editorialLog("AAF copy directory does not\nexist. Set a valid directory and try again.")
            # self.execMessage("\nExecuted Avid Plugin Successfully\nRefer to e-mail for more info.\nCould not find AAF destination folder, please import AAFs manually.")
            self._execMessage += "\nCould not find AAF destination folder, please import AAFs manually."
            log("Could not find AAF destination folder: %s" % destinationFolder)

        # Automatically create a PDF file during publish
        if shotCutList.mode.get('[avidAutoGeneratePDF]') == '1':
            # convert new shots into indices
            newPanelIndices = []
            index = 0
            panelIndex = 0
            for newShot in avidWorkflow.newShots:
                while index < len(shotCutList):
                    shot = shotCutList[index]
                    if shot.isMarker():
                        index += 1
                        continue
                    if shot.label == newShot.label:
                        newPanelIndices.append(panelIndex)
                        break
                    index +=1
                    panelIndex +=1

            toPDF = flix.plugins.toPDF.ToPDF9()
            toPDF.execute(shotCutList, [], {'newShots': newPanelIndices})

        log("To Avid:: Publish Complete with status: %s" % result)

        return "%s" % result

    def emailSummary(self):
        # publish the cutlist
        publishSummary = self.getSummary()

        # # save publish summary
        publishPath      = AvidWorkflow().getPublishPath(self.__shotCutList)
        publishDirectory = os.path.dirname(publishPath)
        if not self.fileServiceLocal.exists(publishDirectory):
            self.fileService.createFolders(publishDirectory)
        self.fileService.saveUtfTextFile(publishPath, urllib.unquote_plus(str(publishSummary)).decode('utf8'))
        # email publish summary
        try:

            show = self.__shotCutList.show
            sequence = self.__shotCutList.sequence

            # grab tracking code for sequence
            trackingCode = Sequence(show, sequence).getTrackingIndex()
            mode = self.__shotCutList.mode
            kargs = {}
            # compile subject
            kargs['[trackingCode]']        = (" %s" % trackingCode).rstrip()
            kargs['[sequenceInfo]']        = "[show]/[sequence][trackingCode]"
            kargs['[result]']              = '' if len(self.__errors)==0 else 'INCOMPLETE '
            kargs['[emailSubjectMessage]'] = "[result]To Avid [sequenceInfo]"
            kargs['[emailSubjectComment]'] = self.__comment

            # email summary
            log("Avid: Emailing Publish Summary: %s" % kargs)
            with mode.using(kargs):
                flix.utilities.email.sendHtmlEmail(
                    '[defaultEmailSender]', '[emailToEditorial]',
                    '[emailFullSubject]', publishSummary, mode)

        # email error to support
        except Exception, e:
            log('Publish email summary failed.%s' % e, trace=True, isError=True)
            subject = "Avid '%s'" % self.__shotCutList.mode[kParamShotCutListFile]
            flix.utilities.email.sendSupportErrorEmail(subject, e)
        return

    def getSummary(self):
        publishTemplateName = self.__shotCutList.mode[kParamPublishTemplate]
        publishSummary      = flix.utilities.template.render(publishTemplateName, **{
            'cutlist'          : self.__shotCutList,
            'cutlistReference' : self.__referenceCutList,
            'newShots'         : self.__newShots,
            'errors'           : self.__errors,
            'FailedDialogues'   : self._dialogueErrors,
            'comment'          : self.__comment,
            'encodingTime'     : self.__encodingTime
        })
        return publishSummary
