from flix.core2.markerList import MarkerList
from flix.web.serverSession import ServerSession

import flix
import flix.core2.mode
import flix.fileServices
import flix.fileServices.fileLocal
import flix.fileServices.repathDefault
import flix.web.serverSession
import flix.plugins.pluginDecorator

from flix.core2.markerList import MarkerList
from flix.plugins.toShotgun import ToShotgun
from flix.plugins.toMov import ToMov
import flix.remote

import os
import sys

import inspect


_UPPER_LINE_Y_OFFSET = 150
_LOWER_LINE_Y = 50
_UPPER_LINE_H = 100
_LOWER_LINE_H = 100

_SEQUENCE_KEY = 'Sequence'
_VERSION_KEY = 'Version'
_START_FRAME_KEY = 'StartFrame'
_END_FRAME_KEY = 'EndFrame'
_PRERENDER_KEY = 'Prerendered'
_FONT_COLOR_KEY = 'FontColor'
_FONT_SIZE_KEY = 'FontSize'
_SHOTS_KEY = 'Shots'
_SCRIPT_NAME_KEY = 'ScriptName'

_PANEL_PATH_KEY = 'PanelPath'


## Shamelessly stolen from flix.rendering.__init__
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


def validateUnicodeChars(text):
    for char in text:
        if ord(unicode(char)) > 128:
            text = text.replace(char, str(ord(unicode(char))))
    return text


## ToDo - Give this class a proper name
class NukeTestEA(ToShotgun):
    """
    A Flix plugin for compositing slate information and uploaded it to Shotgun
    
    Attributes:
        fileService: I don't know what this is
        fileServiceLocal: I don't know what this is
        serverSession: I don't know what this is
        repath: I don't know what this is
        panelList: A list of I don't know what this is
        shotlist: The ShotCutList to operate on
        kargs: I don't know what this is.
        mode:
        sg:
        sgShow:
        sgSeq: 
        seqUrl: I don't what this is. Looks like it's used for Shotgun comments
        markIn: 
        markOut:
    """
    
    ## Note - markIn and markOut probably shouldn't be attributes, but that's
    ## how the Foundry initially wrote them and I'm not sure how they're used
    ## elsewhere in the class inheritance heirarchy, so they stay for now.
    
    def __init__(self):
        """
        Initialize the NukeTestEA plugin
        
        It should be noted that this does not necessarily initialize all of
        the class' attribute variables, as horrifying as that sounds.
        """
        self.fileService = flix.fileServices.FileService()
        self.fileServiceLocal = flix.fileServices.fileLocal.FileLocal()
        self.serverSession = flix.web.serverSession.ServerSession()
        self.repath = flix.fileServices.repathDefault.RepathDefault()

        self.panelList = []

        # load the icon
        iconPath = flix.core2.mode.Mode().get('[FLIX_CONFIG_FOLDER]')+'/plugins/icons/custom_icon.png'
        icon = self.fileService.loadByteArray(iconPath)
        
        ## Flix follows what seems to be a very bizarre design pattern.
        ## The top level parent for this class does not implement __init__() so
        ## we cannot call super() to initialize common attributes.
        ## Instead the top level parent implements an init() function.
        ## My only guess is that this is to pretend the top level parent
        ## is an abstract class and prevent direct instantion.
        ## But why not use the abc module to make a real abstract base class?
        self.init(label='Nuke Test EA',
                  icon=icon,
                  tooltip='This Button Is Only A Test',
                  group='Export',
                  pluginPath='flixConfig.plugins.nukeTestEA.NukeTestEA')

    ## ToDo - Remove this when we have things working and are willing to enter 
    ## production. The following code is a partially commented out version of 
    ## the ToShotgun.execute() function.
    ## In the end, that should be the code that runs, not this.
    ##
    ## I messed up and edited the code. I don't think the above approach would
    ## actually work, anyways. There doesn't seem to be a way to access the 
    ## Marker information from within createMov(), and we need the marker in
    ## order to pull the shot label. It seems like that should be accessible
    ## via the Shot object itself, since the UI displays it when selecting a 
    ## panel in Flix, but that doesn't seem to be the case.
    def execute(self, shotCutList, selection, additionalData=None):
        if not additionalData is None:
            referenceCutList = additionalData.get('reference', None)
            comment = additionalData.get('comment', "")
        else:
            comment = ''
            
        flix.logger.log(comment)
        ## ToDo - Do we even need this comment stuff? It never gets used.
        # comment = unicode(urllib.unquote_plus(comment))
        self.shotList = flix.core2.shotCutList.ShotCutList.fromFile(shotCutList.defaultPath())
        self.kargs = {'show'    :self.shotList.show,
                      'sequence':self.shotList.sequence,
                      'branch'  :self.shotList.branch,
                      'version' :self.shotList.version}
        self.mode = self.shotList.mode

        self.addProgress(4)
        
        ## ToDo - Move this stuff to it's own function
        ## It may be possible to just delete this - it also gets set when
        ## calling getPrerenderedStatus(), which is also when it gets used.
        self.sg = self._connectToSG(self.mode)
        self.removeProgress()

        self.seqUrl = self.getSequenceUrl()
        
        ## Question for Foundry - These lines are effectively duplicated in 
        ## getPrerenderedStatus(). Should only one or the other be used?
        ## Should they be declared in __init__ and have this and the calls
        ## in getPrerenderedStatus() moved to a setter instead?
        # validate that all information for Flix has an equivalent in shotgun
        #self.sgShow = self._validateShow(self.shotList.show)
        #self.sgSeq = self._validateSeqs(self.shotList.sequence)

        self.removeProgress()

        ## Let it be known that getMarkerList() does not return a MarkerList.
        ## It instead returns a list of ShotCutLists.
        ## Because I don't know.
        shotCutLists = self.getMarkerList(self.shotList)
        self.removeProgress()
        
        ## ToDo - If shotCustLists is None, bad things happen
        ## shotCutLists should never be None - if getMarkerList fails to create
        ## a ShotCutList, it returns an empty list.
        ## I don't think the empty list can break this function, but it does
        ## have disturbing implications for uses elsewhere.
        if not shotCutLists:
            shotCutLists.append(self.shotList)
        
        ## This is bad. I'm just hoping that markerList is the same length and
        ## matches self.shotList index-for-index. Ideally this would be handled
        ## inside toMov() so that the shot and marker are definitely matched.
        ## Calling fromShotCutList on the ShotCutList that gets passed returns
        ## an empty list, however.
        markerList = MarkerList.fromShotCutList(self.shotList)
        
        self.addProgress(len(shotCutLists))
        self.markIn = 1
        self.markOut = 0
        
        ## In the original Flix code this is adapted from, scl and shotCutLists
        ## were named 'markerShot' and 'markerShotLists'. Those names were lies
        ## and have been changed here to reflect the actual object types.
        for i, scl in enumerate(shotCutLists):
            ## Question for Foundry - When is a ShotCutList not a Marker?
            ## What does it mean for a ShotCutList to be a Marker?
            ## All tests so far have never entered the else clause of the
            ## following statement. Is that expected?
            if scl.isMarker:
                for shot in scl:
                    self.markOut += int(round(shot.duration))
                
                ## ToDo - Uncomment this once we're willing to check things
                ## against Shotgun again
                #self.sgShot = self._validateShot(scl)
                #self._validateVersion(scl)
                
                flix.logger.log('CALLING NUKETESTEA.CREATEMOV')
                movie = self.createMov(scl, markerList[i])
                ## The += was taken from regular Flix code, but I think it's
                ## a bug, since it very quickly results in markIn being
                ## thousands of frames ahead of markOut.
                # self.markIn += self.markOut
                self.markIn = self.markOut
                
                ## ToDo - Uncomment this once we're willing to
                ## check against/upload to Shotgun again
                #if not self.sgShot:
                #    self.sgShot = self.createSgShot(scl)
                #sgVersion = self.uploadSeqVersion(movie, self.sgShot, comment=comment)
            else:
                pass  # ToDo - Debug. Remove later.

                #self._validateVersion(scl)
                #self.sgTask = self._validateTask()
                #movie = self.createMov(scl)
                #sgVersion = self.uploadSeqVersion(movie, self.sgSeq,
                #                                  self.sgTask, comment=comment)
                
            ## Why does this time out after compositing the first sequence?
            ## Why does it composite the first sequence multiple times?

            ## ToDo - Uncomment this stuff once we're compositing
#            self.playlist = self._validatePlaylist()

#            self.updatePlaylist(self.playlist, sgVersion)
            self.removeProgress()
            
        ## ToDo - Uncomment this once we're composing and willing to upload
        ## to Shotgun
#        ToShotgun.toFile(self, **self.kargs)
#
#        autoMarkOmittedShots = self.mode['[sgAutoMarkOmittedShots]'] == "1"
#
#        if autoMarkOmittedShots:
#            self.autoMarkOmittedShots()

        self.removeProgress()
        
    def createMov(self, shotCutList, marker):
        """
        Composite the slate information onto a ShotCutList
        
        Args:
            shotCutList: The ShotCutList to composite
            marker: The Marker corresponding to shotCutList
            
        Returns:
            The path to the composited movie
        """
        ## ToDo - I'm not sure if the description of the return value above is
        ## correct, as I have not yet been able to test that far.
        
        ## Get information to composite
        fontColor = self.mode['[burnInTopFontColor]']
        fontSize = self.mode['[burnInTopFontSize]']
        prerendered = self.getPrerenderedString(shotCutList)
        version = shotCutList.version
        
        ## ToDo - Remove the target folder override when done testing
        nukeFolder = self.mode['[localFolder]']
        # nukeFolder = 'G:/flix/temp/'
        
        shots = []
        for shot in shotCutList:
            kargs = {'beat': shot.beat,
                     'setup': shot.setup,
                     'version': shot.version,
                     'frame': '%04d'}
            path = shotCutList.mode.get('[recipeCompedFile]', kargs)
            shotInfo = {_PANEL_PATH_KEY: path,
                        _START_FRAME_KEY: shot.markInFrame,
                        _END_FRAME_KEY: shot.markOutFrame}
            shots.append(shotInfo)
        
        # ToDo - Consider turning info_dict into a class to make behavior
        # data-driven and more customizable
        ## Can probably delete most of this. Keeping for now for debug purposes.
        info_dict = {}  
        info_dict[_SEQUENCE_KEY] = marker.name
        info_dict[_VERSION_KEY] = str(version)
        info_dict[_START_FRAME_KEY] = self.markIn # This number is seriously messed up
        info_dict[_END_FRAME_KEY] = self.markOut
        info_dict[_PRERENDER_KEY] = prerendered
        info_dict[_FONT_COLOR_KEY] = fontColor
        info_dict[_FONT_SIZE_KEY] = fontSize
        info_dict[_SHOTS_KEY] = shots
        
        mov = ToMovEA()
        flix.logger.log('\n\n>>>>>>>>>> CALLING TOMOVEA>COMPBUILD() <<<<<<<<<<\n')
        mov.compBuild(shotCutList, info_dict)
        
        ## ToDo - Uncomment this when we are ready to test compositing.
        movPath = self.repath.localize(mov.movieName)
        # movPath = 'G:/You/Might/Want/To/Look/At/nukeTestEA/ToDos'
        flix.logger.log('movPath: {}'.format(movPath))
        return movPath


    def getPrerenderedString(self, shotCutList):
        """
        Query Shotgun if a sequence should be prerendered and format as str
        
        Args:
            shotCutList: the ShotCutList to pull information for
            
        Returns:
            'Prerendered' if the sequence should be prerendered
            'Realtime' otherwise
        """
        
        prerendered = self.getPrerenderedStatus(shotCutList)
        if prerendered:
            return 'Prerendered'
        return 'Realtime'
        
    def getPrerenderedStatus(self, shotCutList):
        """
        Query Shotgun for if a sequence should be prerendered or realtime
        
        Args:
            shotCutList: the ShotCutList to pull information for
        
        Returns:
            True if the sequence should be prerendered
            False otherwise
        """
        
        self.sg = self._connectToSG(shotCutList.mode)
        
        self.sgShow = self._validateShow(shotCutList.show)
        self.sgSeq = self._validateSeqs(shotCutList.sequence)
        
        pFilters = [['id', 'is', self.sgSeq['id']]]
        pFields = ['sg_pre_rendered']
        shot = self.sg.find_one('Sequence', pFilters, pFields)
        
        prerendered = False
        if shot:
            prerendered = True
            # if shot['sg_pre_rendered']:
            #     prerendered = True
                
        return prerendered

## This class should probably be moved to its own module, but I don't want to
## deal with sys.path not containing the plugins folder at the moment.
class ToMovEA(ToMov):
    def __init__(self):
        super(ToMovEA, self).__init__()
        
    def compBuild(self, shotList, info_dict):
        if isinstance(shotList, tuple):
            self.indices = shotList[1]
            shotCutList = shotList[0]
        else:
            shotCutList = shotList
        
        mode = shotCutList.mode
        with mode.using({'branch':shotCutList.branch}):
            self.setKargs(shotCutList, mode)
            
            self.movieName = self._getMovName(mode)
            self.fileService.copyToLocal(self.movieName)
            # if self.fileServiceLocal.exists(self.movieName):
                # flix.logger.log('Movie already exists. Returing early.')
                # return
                
            jpgFilename = '{0}.%04d.jpg'.format(os.path.basename(self.movieName))
            self.imgSeqOutput = '/'.join([self.movieName.replace(os.path.splitext(self.movieName)[-1], '.tmp'), jpgFilename])
            self.movieName = self.movieName.replace(os.path.splitext(self.movieName)[-1], '.tmp{0}'.format(os.path.splitext(self.movieName)[-1]))
            
            self.createCompDir(mode)
            
            self.updateNukeComp(shotCutList, mode)
            
            ## Try to comp evertying directly to a movie instead of comping and then merging an image sequence
            ## Note: this loses the audio and all of that
            # test_destination, ext = os.path.splitext(self.nukeComp['destination'])
            # test_destination, ext = os.path.splitext(test_destination)
            # self.nukeComp['destination'] = test_destination
            
            destination = self.repath.localize(self.nukeComp['destination'])
            flix.logger.log('destination localized: {}'.format(destination))
            
            ## Hopefully all of this destination modification stuff is not needed when the code is run on the server
            # destination = os.path.basename(self.nukeComp['destination'])
            # basepath = os.path.join('G:/flix/temp/test/', info_dict[_SEQUENCE_KEY]) + '/';
            # try:
                # os.makedirs(basepath)
            # except OSError:
                # if not os.path.isdir(basepath):
                    # raise
            # destination = os.path.join(basepath, destination)
            self.imgSeqOutput = destination
            self.nukeComp['destination'] = destination
            
            flix.logger.log('\n\nCreating image sequence\n')
            flix.logger.log('self.imgSeqOutput: {}'.format(self.imgSeqOutput))
            flix.logger.log('self.nukeComp["destination"]: {}'.format(self.nukeComp['destination']))
            self.build_nuke_network(info_dict,
                                    validateUnicodeChars(self.nukeComp['destination']),
                                    validateUnicodeChars(self.nukeComp['scriptName']))
            flix.logger.log('\n\nFinished creating image sequence\n')
            
            ## ToDo - uncomment things below this line when ready to test them
            # self._getCompedSoundFile(shotCutList)
            
            # self.createMovie(shotCutList.show,
                             # shotCutList.sequence,
                             # self.movieName,
                             # self.imgSeqOutput,
                             # self.nukeComp['lastFrame'],
                             # self.soundFile)
            
            ## Fun fact: None of the information in self.nukeComp makes it through
            ## the self.build_nuke_network() call. The dictionary is just empty.
            
            
             # self.fileServiceLocal.forceRemoveFolder(os.path.dirname(self.imgSeqOutput))
            
             # self.fileServiceLocal.rename(self.movieName, self.movieName.replace('.tmp', '')
             # self.movieName = self.movieName.replace()
             
    ## Flix is unable to import the nuke module locally. This decorator
    ## should fix that problem by pushing the function to the Nuke server.
    ## Note that this means any logged information from this scope will appear
    ## in the remote log and not the local one.
    @flix.remote.autoRemote(flix.remote.kProcGroupNuke, lockProc=False)
    def build_nuke_network(self, info_dict, destination, script_name):
        """
        Construct a node network in Nuke for compositing slate information.
        
        This function is no longer being used and is only kept around for the
        purpose of referencing how to set up a node network in Nuke.
        
        Args:
            info_dict: the dictionary containing the slate information
            comp_info: self.nukeComp['destination']
            
        Returns:
            False if errors were encountered in trying to construct the network
            True otherwise
        """
        
        ## Nuke doesn't like to be imported locally.
        ## It only works when run on the server.
        try:
            import nuke
        except:
            return False
            
        def _make_text_node(node_name, text, x=0, y=0, w=200, h=100):
            """
            Create a text node in Nuke with the given text and dimensions
            
            Args:
                node_name: the name to give the node
                text: the message text to assign the node
            
            Kwargs:
                x: The x coordinate to give the left side of the text's bounding box
                y: The y coordinate to give the bottom of the text's bounding box
                w: The width to give the bounding box
                h: The height to give the bounding box
                
            Returns:
                A Nuke Text node
            """
            
            ## Create a Text node rather than the newer Text2 to avoid the
            ## Text2's 'freetype' nonsense moving the text arbitrarily
            node = nuke.createNode('Text')
            node['message'].setText(text)
            node['box'].setX(x)
            node['box'].setY(y)
            node['box'].setR(x+w)
            node['box'].setT(y+h)
            return node
        
        flix.logger.log('\n>>>>> COMPOSITING {} <<<<<\n\n'.format(info_dict[_SEQUENCE_KEY]))
        
        flixNuke = FlixNuke()
        flixNuke.clearScript()
        
        nuke.root().knob('first_frame').setValue(info_dict[_START_FRAME_KEY])
        nuke.root().knob('last_frame').setValue(info_dict[_END_FRAME_KEY])
        nuke.root().knob('frame').setValue(info_dict[_START_FRAME_KEY])
        
        read_nodes = []
        for shot in info_dict[_SHOTS_KEY]:
            read_node = nuke.nodes.Read(name='FileInput')
            read_node.setXpos(1)
            read_node.setYpos(1)
            
            ## ToDo - Switch which version of envized is used once we have
            ## a dev server up to test composition on - the environment variable
            ## isn't set on my local machine

            ## The envize functions normally strip out the garbage folder flix
            ## automatically adds to the start of paths for reasons unknown
            panelPath = shot[_PANEL_PATH_KEY]
            panelPath = panelPath[len('/shots'):]
            panelPath = panelPath + ' {0}-{1}'.format(shot[_START_FRAME_KEY],
                                                      shot[_END_FRAME_KEY])
            # envized = 'G:/flix/flixProjects' + panelPath
            envized = '/Applications/Flix/flixProjects' + panelPath
            envized = self.repath.envizeForNuke(envized)
            flix.logger.log('envized: {}'.format(envized))
            
            read_node['file'].fromUserText(envized)
            read_nodes.append(read_node)
        
        image_width = read_nodes[0].format().width()
        image_height = read_nodes[0].format().height()
        
        upper_y = image_height - _UPPER_LINE_Y_OFFSET
        
        sequence_node = _make_text_node('SequenceText',
                                       info_dict[_SEQUENCE_KEY],
                                       x=50,
                                       y=upper_y,
                                       w=1150,
                                       h=_UPPER_LINE_H)
                                       
        prerender_node = _make_text_node('PrerenderText',
                                         info_dict[_PRERENDER_KEY],
                                         x=1200,
                                         y=upper_y,
                                         w=600,
                                         h=_UPPER_LINE_H)
                                         
        date_node = _make_text_node('DateText',
                                    '[date %D]',
                                    x=50,
                                    y=_LOWER_LINE_Y,
                                    w=450,
                                    h=_LOWER_LINE_H)
                                    
        version_node = _make_text_node('VersionText',
                                       'Version {}'.format(info_dict[_VERSION_KEY]),
                                       x=350,
                                       y=_LOWER_LINE_Y,
                                       w=400,
                                       h=_LOWER_LINE_H)
        
        write_node = nuke.createNode('Write')
        
        destination = self.repath.localize(destination)
        
        ## Ensure that there is a folder to save composited images to
        dirname = os.path.dirname(destination)
        try:
            os.makedirs(dirname)
        except OSError:
            if not os.path.isdir(dirname):
                raise
                
        write_node['file'].fromUserText(destination)
        
        sequence_node.setInput(0, read_nodes[0])
        prerender_node.setInput(0, sequence_node)
        date_node.setInput(0, prerender_node)
        version_node.setInput(0, date_node)
        write_node.setInput(0, version_node)
        
        script_name = self.repath.localize(script_name)
        flix.logger.log('Saving nuke recipe file as {}'.format(script_name))
        nuke.scriptSave(script_name)
        
        nuke.execute(write_node['name'].getValue())
        
        FlixNuke().clearScript()
        
        flix.logger.log('\n>>>>> FINISHED COMPOSITING {} <<<<<\n\n'.format(info_dict[_SEQUENCE_KEY]))
        
        return True
    
    ## May not need this stuff. Stolen from elsewhere in Flix.
    # def ffmpegExtractCalculateDeadline(self, show, sequence, movieName, imgSequence, duration, audioFile=""):
        # totalDuration = len(self.fileServiceLocal.listFolder(os.path.dirname(imgSequence)))
        # flix.logger.log('ffmpeg deadline %s' % totalDuration)
        # return max(100, totalDuration * 5)
    
    # @flix.remote.autoRemote(flix.remote.kProcGroupMov, calculateDeadlineFunction=ffmpegExtractCalculateDeadline)
    # def createMovie(self, show, sequence, movieName, imgSequence, duration, audioFile=""):
        # mode = flix.core2.mode.Mode(show, sequence)
        # ffmpeg = os.environ.get('FLIX_FFMPEG')
        # imgSequence = self.repath.localize(imgSequence)
        # self.fileService.copyToLocal(movieName)
        # movieName = self.repath.localize(movieName)
        # if self.fileServiceLocal.exists(movieName):
            # return
        # frameRate = float(self._getFrameRate(mode))
        # if audioFile:
            # audioFile = "-i '%s' -c:a copy"%self.repath.localize(audioFile)
        # self.setLibraryPaths()
        # command = '"%(ffmpeg)s" -f image2 -framerate %(frameRate)s -i "%(imgSequence)s" %(audioFile)s -vf fps=fps=%(frameRate)s -frames:v %(duration)s "%(movieName)s"'%locals()
        # flix.logger.log('>>>>>ffmpeg command: {}'.format(command))
        # result = flix.utilities.osUtils.OSUtils.quickCall(command, cwd=os.path.dirname(ffmpeg))