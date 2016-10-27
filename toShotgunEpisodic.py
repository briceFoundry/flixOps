#!/usr/bin/env python
#------------------------------------------------------------------------------
# toShotgunGEAH.py - shotgun publish tool from Flix, customized for Green Eggs & Ham
#------------------------------------------------------------------------------
# Copyright (c) 2014 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

import os
import urllib

from flix.fileServices                import FileService
from flix.fileServices.repathDefault  import RepathDefault
from flix.core2.shotCutList           import ShotCutList
from flix.core2.mode                  import Mode
from flix.core2.markerList            import MarkerList
from flix.utilities.log               import log as log

from flix.plugins.toShotgun           import ToShotgun, ShotgunExceptions
from flix.web.serverSession           import ServerSession

# import flix.core2.shotCutList
import flix.remote
import flix.logger

# -----------------------------------------------------
# Global Varaibles
# -----------------------------------------------------

serverSession = ServerSession()
fileService = FileService()

KparamSGserver        = '[sgServerPath]'
KparamSGscript        = '[sgScriptName]'
KparamSGkey           = '[sgScriptKey]'
KparamSGstoTask       = '[sgStoryTaskName]'
KparamSGshowField     = '[sgFieldShowName]'
KparamSGsequenceField = '[sgFieldSequenceName]'
KparamSGversionName   = '[sgVersionName]'
KparamSGshotName      = '[sgShotName]'


class ToShotgunEpisodic(ToShotgun):

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self):
        self.fileService = fileService
        self.rePath      = RepathDefault()


        self.shotList             = ''
        self.sg                   = None
        self.sgShow               = ''
        self.sgSeq                = ''
        self.sgShot               = ''
        self.sgTask               = ''

        # load the icon
        iconPath = Mode().get('[FLIX_FOLDER]')+'/assets/20px-shotgun.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label     ='Shotgun Publish GEAH',
                  icon      =icon,
                  tooltip   ='Shotgun Publish GEAH',
                  group     ='Editorial',
                  pluginPath='flixConfig.plugins.toShotgunEpisodic.ToShotgunEpisodic')

    #--------------------------------------------------------------------------
    # executions
    #--------------------------------------------------------------------------

    def execute(self, shotCutList, selection, additionalData=None):
        if not additionalData is None:
            referenceCutList = additionalData.get('reference', None)
            comment = additionalData.get('comment', "")
        else:
            comment = ''

        comment = unicode(urllib.unquote_plus(comment))
        self.shotList = flix.core2.shotCutList.ShotCutList.fromFile(shotCutList.defaultPath())
        self.kargs = {'show'    :self.shotList.show,
                 'sequence':self.shotList.sequence,
                 'branch'  :self.shotList.branch,
                 'version' :self.shotList.version}
        self.mode = self.shotList.mode

        self.addProgress(4)

        markerShotLists = self.getMarkerList(self.shotList)

        self.removeProgress()
        self.sg = self._connectToSG(self.mode)
        self.removeProgress()

        self.seqUrl = self.getSequenceUrl()

        # validate that all information for Flix has an equivalent in shotgun
        self.sgShow = self._validateShow(self.shotList.show)
        if int(Mode(self.shotList.show).get('[isEpisodic]')):
            episodeName = self.shotList.sequence.split("_")[0]
            self.sgEp = self._validateEp(episodeName)
            sequenceName = "_".join(self.shotList.sequence.split("_")[1:])
            self.sgSeq = self._validateSeqs(sequenceName)
        else:
            self.sgEp = None
            self.sgSeq = self._validateSeqs(self.shotList.sequence)

        self.removeProgress()

        # check for shots to create movies and upload to shotgun as version
        # if shots don't exists yet create a movie of the entire sequence and upload to shotgun as version

        if not markerShotLists:
            markerShotLists.append(self.shotList)

        self.addProgress(len(markerShotLists))
        self.markIn = 1
        self.markOut = 0
        for markerShot in markerShotLists:
            if markerShot.isMarker:
                for shot in markerShot:
                    self.markOut += int(round(shot.duration))
                self.sgShot = self._validateShot(markerShot)
                self._validateVersion(markerShot)
                tupleMarker = (markerShot, self.getShotsIndex(markerShot))
                movie = self.createMov(tupleMarker)
                self.markIn += self.markOut
                if not self.sgShot:
                    self.sgShot = self.createSgShot(markerShot)
                sgVersion = self.uploadSeqVersion(movie, self.sgShot, comment=comment)
            else:
                self._validateVersion(markerShot)
                self.sgTask = self._validateTask()
                movie = self.createMov(markerShot)
                sgVersion = self.uploadSeqVersion(movie, self.sgSeq,
                                                  self.sgTask, comment=comment)

            # Validate that a FLIX playlist exists or else create one
            self.playlist = self._validatePlaylist()

            # update the FLIX playlist to add the new sgVersion
            self.updatePlaylist(self.playlist, sgVersion)
            self.removeProgress()

        ToShotgunGEAH.toFile(self, **self.kargs)

        autoMarkOmittedShots = self.mode['[sgAutoMarkOmittedShots]'] == "1"

        if autoMarkOmittedShots:
            self.autoMarkOmittedShots()

        self.removeProgress()

    #--------------------------------------------------------------------------
    # helpers
    #--------------------------------------------------------------------------

    def _validateEp(self, episode):
        epField = 'sg_flixepname'
        pFilters = [['project', 'is', self.sgShow], 
                    [epField, 'is', episode]]
        pFields = ['id', 'code', 'sg_flixepname']
        # Won't always be 'CustomEntity01', that needs to be checked on a case per case basis
        sgEp = self.sg.find_one('CustomEntity01', pFilters, pFields)
        if sgEp:
            return sgEp
        else:
            raise ShotgunExceptions(msg="Could not find '%s' Episode in SG" % episode)

    #--------------------------------------------------------------------------

    def _validateSeqs(self, sequence):
        if self.sgEp is None:
            sequenceField = self.mode[KparamSGsequenceField]
            sFilters = [['project', 'is', self.sgShow],
                        [sequenceField, 'is', sequence]]
        else:
            sequenceField = 'sg_flixseqname'
            sFilters = [['project', 'is', self.sgShow],
                        ['sg_episode', 'is', self.sgEp],
                        [sequenceField, 'is', sequence]]
        sFields = ['id', 'content', sequenceField, 'sg_status_list']
        sgSeq = self.sg.find_one('Sequence', sFilters, sFields)
        if sgSeq:
            return sgSeq
        else:
            raise ShotgunExceptions(msg="Could not find '%s' Sequence in SG" % sequence)

    #--------------------------------------------------------------------------

    def autoMarkOmittedShots(self):
        """
        Go through all the shots in shotgun and set the Omit status if a shot is not part of the edit
        :return:
        """
        shotNames = []
        markerIndex = 1
        for shot in self.shotList:
            if shot.isMarker():
                markerIndex, markerName = MarkerList.getMarkerName(shot, markerIndex)
                shotNames.append(markerName)

        if len(shotNames) == 0:
            flix.logger.log('No shots were found in the edit')
            return

        pFilters = [['sg_sequence', 'is', self.sgSeq]]
        pFields = ['id', 'code', 'sg_status_list']
        allShots = self.sg.find('Shot', pFilters, pFields)
        for shot in allShots:
            if shot['code'] not in shotNames:
                self.sg.update('Shot', shot['id'], {'sg_status_list':'omt'})
