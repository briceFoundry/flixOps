#!/usr/bin/env python
#------------------------------------------------------------------------------
# toShotgunGEAH.py - shotgun publish tool from Flix, customized for Green Eggs & Ham
#------------------------------------------------------------------------------
# Copyright (c) 2014 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

import copy
import os
import urllib, urllib2

from flix.fileServices                import FileService
from flix.fileServices.repathDefault  import RepathDefault
from flix.plugins.toMov               import ToMov
from flix.core2.shotCutList           import ShotCutList
from flix.core2.mode                  import Mode
from flix.core2.markerList            import MarkerList
from flix.utilities.log               import log as log
from flix.utilities.audioUtils        import AudioUtils

from flix.plugins.toShotgun           import ToShotgun, ShotgunExceptions
from flix.web.serverSession           import ServerSession

import flix.remote
import flix.logger

from flixConfig.plugins.shotInfo     import ShotInfo
from flixConfig.plugins.toMovPerShot import ToMovPerShot

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

# GEAH Parameters
# kParamSgEpisodeEntity = "CustomEntity01"
# kParamSgShotTaskTemplateId = 17
# kParamSgVersionTaskId = 5492
# kParamSgDialogueField = 'sg_dialogue'
# kParamSgDissolveInField = 'sg_head_in'
# kParamSgDissolveOutField = 'sg_tail_out'

# Foundry Parameters
kParamSgEpisodeEntity = "CustomEntity01"
kParamSgShotTaskTemplateId = 5
kParamSgVersionTaskId = 2359
kParamSgDialogueField = 'sg_dialogue'
kParamSgDissolveInField = 'sg_head_in'
kParamSgDissolveOutField = 'sg_tail_out'


class ToShotgunGEAH(ToShotgun):

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

        self.init(label     ='Shotgun GEAH',
                  icon      =icon,
                  tooltip   ='Shotgun GEAH',
                  group     ='Editorial',
                  pluginPath='flixConfig.plugins.toShotgunGEAH.ToShotgunGEAH')

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
        self.markerShotLists = self.getMarkerList(self.shotList)
        # Get the editorial movie path
        self.addProgress(4)
        self.movDir = self.mode.get("[editorialMOVFolder]")

        movieFileName = self.shotList.refVideoFilename
        if movieFileName is None:
            raise flix.exceptions.FlixException(msg="Current version does not have an editorial movie.", notify=True)
        else:
            movieFile = "%s/%s" % (self.movDir, movieFileName)
            log("Movie File: %s" % movieFile)
        shotInfoObject = ShotInfo(self.shotList)
        shotsInfo = shotInfoObject.getShotsInfo()
        toMovPerShotObject = ToMovPerShot(self.shotList)
        self.addProgress(len(shotsInfo))
        shotMovies = toMovPerShotObject.toMovPerShot(shotsInfo, movieFile)

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

        if not self.markerShotLists:
            self.markerShotLists.append(self.shotList)

        self.addProgress(len(self.markerShotLists))
        for markerShot in self.markerShotLists:
            index = self.markerShotLists.index(markerShot)
            if markerShot.isMarker:
                self.sgShot = self._validateShot(markerShot)
                self._validateVersion(markerShot)
                # dialogue = shotsInfo[index][5]
                movie = shotMovies[index]
                mp3 = movie.replace(".mov", ".mp3")
                AudioUtils().localConvertAudio(movie, mp3)
                if not self.sgShot:
                    # self.sgShot = self.createSgShot(markerShot)
                    self.sgShot = self.createSgShot(markerShot, shotsInfo[index])
                sgVersion = self.uploadSeqVersion(self.rePath.localize(movie), self.rePath.localize(mp3), self.sgShot, comment=comment)
            else:
                self._validateVersion(markerShot)
                self.sgTask = self._validateTask()
                movie = self.createMov(markerShot)
                mp3 = movie.replace(".mov", ".mp3")
                AudioUtils().localConvertAudio(movie, mp3)
                sgVersion = self.uploadSeqVersion(self.rePath.localize(movie), self.rePath.localize(mp3), self.sgSeq,
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
    # Shotgun Methods
    #--------------------------------------------------------------------------
    def _validateEp(self, episode):
        epField = 'sg_flixepname'
        pFilters = [['project', 'is', self.sgShow], 
                    [epField, 'is', episode]]
        pFields = ['id', 'code', 'sg_flixepname']
        sgEp = self.sg.find_one(kParamSgEpisodeEntity, pFilters, pFields)
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
        sFields = ['id', 'code', 'content', sequenceField, 'sg_status_list']
        sgSeq = self.sg.find_one('Sequence', sFilters, sFields)
        if sgSeq:
            return sgSeq
        else:
            raise ShotgunExceptions(msg="Could not find '%s' Sequence in SG" % sequence)

    #--------------------------------------------------------------------------

    def _validateShotTaskTemplate(self):
        """ Gets the Task Template entity that each shot should be assigned (e.g. "Basic shot template")
        """
        tFilters = [['id', 'is', kParamSgShotTaskTemplateId]]
        tFields = ['id']
        sgShotTaskTemplate = self.sg.find_one('TaskTemplate', tFilters, tFields)
        return sgShotTaskTemplate

    #--------------------------------------------------------------------------

    def createSgShot(self, shotList, shotInfo):
        """create a new shotgun shot based on marker name
        """
        shotArgs = copy.copy(self.kargs)
        shotArgs['shot'] = shotList.isMarker
        shotName = self.mode.get(KparamSGshotName, shotArgs)
        taskTemplate = self._validateShotTaskTemplate()
        data  = {'project': self.sgShow,
                 'sg_sequence': self.sgSeq,
                 'code': shotName,
                 'sg_cut_duration': shotInfo['cut duration'],
                 kParamSgDissolveInField: shotInfo['dissolve in'],
                 kParamSgDissolveOutField: shotInfo['dissolve out'],
                 kParamSgDialogueField: shotInfo['dialogue'],
                 'sg_working_duration': shotInfo['working duration'],
                 'task_template': taskTemplate}
        return self.sg.create('Shot', data, ['id', 'code'])

    #--------------------------------------------------------------------------

    def _validateVersionTask(self):
        """ Gets the Task entity that each version should be assigned (e.g. "Final Animatic")
        """
        tFilters = [['id', 'is', kParamSgVersionTaskId]]
        tFields = ['id']
        sgVersionTask = self.sg.find_one('Task', tFilters, tFields)
        return sgVersionTask

    #--------------------------------------------------------------------------

    def uploadSeqVersion(self, movPath, mp3Path, entity, sgTask = '', comment = u''):
        """Uploads the given movie path to the specific entity in shotgun
            adds a link back to FLIX as the comment
        """
        versionArgs = copy.copy(self.kargs)
        versionArgs['version'] = "%03d"%versionArgs['version']
        versionArgs['shot'] = entity.get('code', '')

        versionName = self.mode.get("%s_%s_%s" % (self.sgEp["code"], self.sgSeq["code"], versionArgs["shot"]), versionArgs)

        description = "%s,\n%s %s %s" % (comment, self.sgEp["code"], self.sgSeq["code"], versionArgs["version"]) 

        data  = {'project': self.sgShow,
                 'code': versionName,
                 'description':description,
                 'sg_path_to_movie' : movPath,
                 'entity' : entity,
                 'sg_task': self._validateVersionTask()}
        if sgTask:
            data['sg_task'] = sgTask

        if not self.sgVersion:
            self.sgVersion = self.sg.create('Version', data, ['id'])
        else:
            self.sg.update('Version', self.sgVersion['id'], data)
        successUpload = False
        tryIter = 1
        while not successUpload:
            try:
                self.fileService.refreshCache(movPath)
                self.sg.upload('Version', self.sgVersion['id'], movPath, 'sg_uploaded_movie')
                self.sg.upload('Version', self.sgVersion['id'], mp3Path, 'sg_uploaded_audio')
                successUpload = True
                return self.sgVersion
            except urllib2.URLError, err:
                if tryIter < 3:
                    tryIter += 1
                    log('Failed to connect\nAttempt %01d of 3 to connect to SG'%int(tryIter), isWarning=True)
                    continue
                raise err

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
