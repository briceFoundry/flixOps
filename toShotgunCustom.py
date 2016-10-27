#!/usr/bin/env python
#------------------------------------------------------------------------------
# toShotgun.py - shotgun publish tool from Flix
#------------------------------------------------------------------------------
# Copyright (c) 2014 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

import os
import urllib2, urllib
import copy

from flix.fileServices                import FileService
from flix.fileServices.repathDefault  import RepathDefault
from flix.plugins.toMov               import ToMov
from flix.core2.shotCutList           import ShotCutList
from flix.utilities.log               import log as log
import flix.exceptions
from shotgun_api3                     import Shotgun, lib


from flix.plugins.pluginDecorator     import PluginDecorator
from flix.core2.mode                  import Mode
from flix.web.serverSession           import ServerSession
from flix.core2.markerList           import MarkerList

import flix.core2.shotCutList
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

#--------------------------------------------------------------------------
# Exceptions
#--------------------------------------------------------------------------
class ShotgunExceptions(flix.exceptions.FlixException):
    def __init__(self, msg="", error=None, notify=True):
        self.error = error
        self.msg = msg
        super(ShotgunExceptions, self).__init__(msg, error, notify)


class ToShotgunCustom(PluginDecorator):

    #--------------------------------------------------------------------------
    # Static
    #--------------------------------------------------------------------------
    @staticmethod
    def toFile(obj, **kwargs):
        ''' write out the shotgun publish
        '''
        sgPubPath = obj.shotList.mode.get('[sgPublishFolder]', kwargs)
        if fileService.exists(sgPubPath):
            fileService.copyToLocal(sgPubPath)
            return
        if not fileService.exists(os.path.dirname(sgPubPath)):
            fileService.createFolders(os.path.dirname(sgPubPath))
        log(sgPubPath, isInfo=True)
        fileService.saveJsonFile(sgPubPath, kwargs)

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self):
        self.fileService = fileService
        self.rePath      = RepathDefault()


        self.shotList             = ''
        self.sg                   = None
        self.sgShow              = ''
        self.sgSeq               = ''
        self.sgShot              = ''
        self.sgTask              = ''

        # load the icon
        iconPath = Mode().get('[FLIX_FOLDER]')+'/assets/20px-shotgun.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label     ='Shotgun Publish Custom',
                  icon      =icon,
                  tooltip   ='Shotgun Publish Custom',
                  group     ='Editorial',
                  pluginPath='flixConfig.plugins.toShotgunCustom.ToShotgunCustom')

    #--------------------------------------------------------------------------
    # executions
    #--------------------------------------------------------------------------

    def shotgunPublish(self, source, output):
        setattr(self, 'shotList', ShotCutList.fromFile(source))
        self.execute(self.shotList, [], output)

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
            sequenceName = self.shotList.sequence.split("_")[1]
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

        ToShotgunCustom.toFile(self, **self.kargs)

        autoMarkOmittedShots = self.mode['[sgAutoMarkOmittedShots]'] == "1"

        if autoMarkOmittedShots:
            self.autoMarkOmittedShots()

        self.removeProgress()

    #--------------------------------------------------------------------------
    # methods
    #--------------------------------------------------------------------------

    @flix.remote.autoRemote(flix.remote.kProcGroupFile, lockProc=False)
    def getPublishedVersions(self, show, sequence, branch):
        """Return an array of the versions that were published to editorial
        """
        matches = Mode(show, sequence).getMatches('[sgPublishFolder]', {'version':'*'})
        versions = []
        for m in matches:
            try:
                versions.append(int(m['version']))
            except ValueError:
                pass
        return versions

    #--------------------------------------------------------------------------
    @flix.remote.autoRemote(flix.remote.kProcGroupFile, lockProc=False)
    def getPublishedSetups(self, show, sequence):
        """Return an array of the versions that were published to editorial
        """
        pass

    #--------------------------------------------------------------------------

    def createMov(self, shotList):
        """creates a movie of the given shotcutlist
        """
        toMov = ToMov()
        toMov.compBuild(shotList)
        return self.rePath.localize(toMov.movieName)

    #--------------------------------------------------------------------------

    def uploadSeqVersion(self, movPath, entity, sgTask = '', comment = u''):
        """Uploads the given movie path to the specific entity in shotgun
            adds a link back to FLIX as the comment
        """
        versionArgs = copy.copy(self.kargs)
        versionArgs['version'] = "%03d"%versionArgs['version']
        versionArgs['shot'] = entity.get('code', '')

        versionName = self.mode.get(KparamSGversionName, versionArgs)

        comment+= "\n%s"% self.seqUrl

        data  = {'project': self.sgShow,
                 'code': versionName,
                 'description':comment,
                 'sg_path_to_movie' : movPath,
                 'entity' : entity}
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
                successUpload = True
                return self.sgVersion
            except urllib2.URLError, err:
                if tryIter < 3:
                    tryIter += 1
                    log('Failed to connect\nAttempt %01d of 3 to connect to SG'%int(tryIter), isWarning=True)
                    continue
                raise err

    #--------------------------------------------------------------------------

    def getShotsIndex(self, markerShotList):
        indices = []
        for index, shot in enumerate(self.shotList):
            if shot in markerShotList:
                indices.append(index)
        return [min(indices), max(indices)]

    #--------------------------------------------------------------------------

    def updatePlaylist(self, playlist, version):
        """Update the FLIX playlist in shotgun to have the latest versions
        """
        pFilters = [['id', 'is', playlist['id']]]
        pFields  = ['versions']
        playlistVersions = self.sg.find_one('Playlist', pFilters, pFields)
        curVersions = playlistVersions['versions']
        for curVer in curVersions:
            if version['id'] == curVer['id']:
                curVersions.remove(curVer)
        curVersions.append(version)
        data = {'versions': curVersions}
        self.sg.update('Playlist', playlistVersions['id'], data)

    #--------------------------------------------------------------------------

    def getSequenceUrl(self):
        '''Check for the current sequence url
           if server and port missing than return arguments
        '''
        server = bool(self.mode.get('[server]') != '[FLIX_SERVER]')
        port = bool(self.mode.get('[port]') != '[FLIX_PORT]')
        if server and port:
            return self.mode.get('[sequenceUrl]', self.kargs)
        else:
            kargs={'server': '127.0.0.1', 'port': '35980'}
            kargs.update(self.kargs)
            return self.mode.get('[sequenceUrl]', kargs)

    #--------------------------------------------------------------------------
    def updateStatus(self, entity, status):
        '''check status of the entity, if status is not final and not
           the same as the requested status, than change status to "in progress"
        '''

        if not entity['sg_status_list'] == 'fin' and not entity['sg_status_list'] == status:
            data = {'sg_status_list':'ip'}
            return self.sg.update(entity['type'], entity['id'], data)
        else:
            return
    #--------------------------------------------------------------------------

    def createSgShot(self, shotList):
        """create a new shotgun shot based on marker name
        """
        shotArgs = copy.copy(self.kargs)
        shotArgs['shot'] = shotList.isMarker
        shotName = self.mode.get(KparamSGshotName, shotArgs)
        data  = {'project': self.sgShow,
                 'sg_sequence': self.sgSeq,
                 'code':shotName,
                 'sg_cut_duration': self.getShotLength(shotList)}
        return self.sg.create('Shot', data, ['id', 'code'])

    #--------------------------------------------------------------------------

    def getShotName(self, shot):
        """Try to get the marker dialog as the label if not get the markers setup name
        """
        poses = shot.recipe.getPoses()
        if len(poses) == 1 and poses[0].get('dialogue', '') != '':
            return poses[0]['dialogue']
        else:
            return shot.recipe.getSetupName()

    #--------------------------------------------------------------------------

    def getMarkerList(self, shotList, hiddenMarker = False):
        """Get a list of markers from the current edit
        """
        markerList = MarkerList.fromShotCutList(shotList)
        markerShotLists = MarkerList.markerShotCutList(shotList, markerList)
        return markerShotLists

    #--------------------------------------------------------------------------
    # helpers
    #--------------------------------------------------------------------------

    def _validateShow(self, show):
        showField = self.mode[KparamSGshowField]
        log("showField: %s" % showField)
        pFilters = [[showField, 'is', show]]
        pFields = ['id', 'name']
        sgShow = self.sg.find_one('Project', pFilters, pFields)
        if sgShow:
            return sgShow
        else:
            raise ShotgunExceptions(msg="Could not find '%s' Project in SG"%show)

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

    def _validateShot(self, shotList):
        shotArgs = copy.copy(self.kargs)
        shotArgs['shot'] = shotList.isMarker
        shotName = self.mode.get(KparamSGshotName, shotArgs)
        pFilters = [['code', 'is', shotName], ['sg_sequence', 'is', self.sgSeq]]
        pFields = ['id', 'code']
        sgShot = self.sg.find_one('Shot', pFilters, pFields)
        if sgShot:
            data = {'sg_cut_duration':self.getShotLength(shotList)}
            self.sg.update('Shot', sgShot['id'], data)
        return sgShot

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
            raise ShotgunExceptions(msg="Could not find '%s' Sequence in SG"%sequence)

    #--------------------------------------------------------------------------

    def _validateTask(self):
        taskName = self.mode[KparamSGstoTask]
        tFilters = [['content', 'is', taskName],
                    ['entity', 'is', self.sgSeq]]
        tFields = ['id', 'content', 'sg_status_list']
        sgTask = self.sg.find_one('Task', tFilters, tFields)
        if sgTask:
            return sgTask
        else:
            message = "Could not find '%s' Task under '%s' in SG"%(taskName, self.sgSeq['code'])
            raise ShotgunExceptions(error="%s\nTo change Task use 'sgStoryTaskName' parameter.",msg=message)

    #--------------------------------------------------------------------------
    def _validatePlaylist(self):
        '''check if a playlist exists, else create a playlist named FLIX
        '''
        pFilters = [['code', 'is', 'FLIX']]
        pFields = ['id']
        playlist = self.sg.find_one('Playlist', pFilters, pFields)
        if playlist:
            return playlist
        else:
            data  = {'project': self.sgShow,
                     'code':'FLIX',
                     'description':'Flix imported Versions'}
            return self.sg.create('Playlist', data, ['id'])

    #--------------------------------------------------------------------------
    def _validateVersion(self, shotList):
        versionArgs = copy.copy(self.kargs)
        versionArgs['version'] = "%03d"%versionArgs['version']
        if getattr(shotList, 'isMarker'):
            versionArgs['shot'] = shotList.isMarker
        else:
            versionArgs['shot'] = versionArgs.get('sequence')

        versionName = self.mode.get(KparamSGversionName, versionArgs)

        filters = [['entity', 'is', self.sgSeq]]
        if self.sgShot:
            filters = [['entity', 'is', self.sgShot]]

        vFilters = [['code', 'is', versionName], {'filter_operator': 'any',
                                                  'filters':filters}]


        self.sgVersion = self.sg.find_one('Version', vFilters)
        log(versionName, isInfo=True)
        log(self.sgVersion, isInfo=True)
        if self.sgVersion:
            raise ShotgunExceptions(msg="A SG version already exists for your current edit.",
                                    error={'moviePath': versionName, 'SGversion': self.sgVersion})


    #--------------------------------------------------------------------------

    def _connectToSG(self, kmode):
        SERVER_PATH = kmode[KparamSGserver]
        SCRIPT_USER = kmode[KparamSGscript]
        SCRIPT_KEY  = kmode[KparamSGkey]
        try:
            SG = Shotgun(SERVER_PATH, SCRIPT_USER, SCRIPT_KEY)
            return SG
        except lib.httplib2.ServerNotFoundError, err:
            raise ShotgunExceptions(msg=err.message, error=err)


    def getShotLength(self, shotList):
        length = 0
        for shot in shotList:
            length += shot.duration
        return int(length)


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
