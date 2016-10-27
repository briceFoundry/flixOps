#------------------------------------------------------------------------------
# toMovDialogue.py - Exports the current version as a QuickTime movie, with dialogue burnt in below the board
#------------------------------------------------------------------------------
# Copyright (c) 2013 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

from flix                        import fileServices
from flix.core2.mode             import Mode
from flix.core2.shotCutList      import ShotCutList
from flix.plugins                import pluginDecorator
from flix.utilities.log          import log as log

import flix
import os

#-----------------------------------------------------
# Global Varaibles
#-----------------------------------------------------

kDialogueHeight = "[toMovDialogueHeight]"
kDialogueFontSize = "[toMovDialogueFontSize]"

#------------------------------------------------------------------------------
# class 
#------------------------------------------------------------------------------

class ToMovDialogue(flix.plugins.toMov.ToMov):

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self):
        self.fileService      = fileServices.FileService()
        self.repath      = fileServices.Repath()
        self.fileServiceLocal = fileServices.fileLocal.FileLocal()
        self.nukeComp         = {}
        self.kargs            = {}
        self.indices          = None
        # load the icon
        iconPath = flix.core2.mode.Mode().get('[FLIX_FOLDER]')+'/assets/20px-quicktime.png'
        icon = self.fileService.loadByteArray(iconPath)
        
        self.init(label='To Movie Dialogue',
                  icon=icon,
                  tooltip='Create a quicktime edit with dialogue burnt in',
                  group='Export',
                  pluginPath='flixConfig.plugins.toMovDialogue.ToMovDialogue')
    
    #--------------------------------------------------------------------------
    # methods
    #--------------------------------------------------------------------------

    def _getStillsList(self, shotList):
        """ Returns a list of panel file location, frame duration and dialogue"""
        stills = list()
        lastFrame  = 0
        for shot in shotList:
            if shot.isMarker():
                continue
            kargs = {'beat'    : shot.beat,
                     'setup'   : shot.setup,
                     'version' : shot.version}
            for frame in range(shot.markInFrame, shot.markOutFrame +1):
                frameDuration  = shot.duration
                dialogue = shot.recipe.getDialogue()
                if shot.isMovie():
                    frameDuration = 1
                kargs['frame'] = "%04d" % frame
                filePath = shotList.mode.get('[recipeCompedFile]', kargs)
                self.fileService.copyToLocal(filePath)
                stills.append([filePath, frameDuration, dialogue])
                lastFrame += frameDuration

        self.nukeComp['lastFrame'] = int(lastFrame)
        return stills

    def createImgSequence(self, source):
        """ Send to nuke services to create nk script """
        flixNuke = FlixNukeCustom()
        flixNuke.toMov(source)

from flix.rendering.flixNukeLocal import FlixNukeLocal
import nuke
import nukescripts

class FlixNukeCustom(FlixNukeLocal):

    @flix.remote.autoRemote(flix.remote.kProcGroupNuke)
    def toMov(self, source):
        """
        Create a standard movie for playback from a fle xml file
        """
        mode = flix.core2.mode.Mode()
        # localize file paths
        compPath   = self.repath.localize(source['compPath'])
        destination = self.validateUnicodeChars(source['destination'])
        scriptName = self.validateUnicodeChars(self.repath.localize(source['scriptName']))

        # set vars for script resolution and frame rate
        xResolution  = source['xResolution']
        yResolution  = source['yResolution']
        frameRate    = source['frameRate']

        # create nukeComp format
        compFormat   = "%d %d %s" % (xResolution, yResolution, "_flix_1_format")
        flixFormat   = nuke.addFormat(compFormat)

        # create read & write node. Define codec and file type
        readNodes     = source['readNodes']
        writeNodeName = self.validateUnicodeChars(source['writeNode'])

        # setup enumeration keys
        kInput1    = 0
        kInputNum  = 0
        kFilePath  = 0
        kReadNode  = 0
        kDuration  = 1
        kDialogue  = 2

        animationKey   = 0
        animationValue = 0
        lastFrame      = 0
        firstFrame     = 1

        # create list for read node objects
        readNodeList = []

        try:
            dialogueHeight = int(mode.get(kDialogueHeight))
        except ValueError, e:
            log("Could not get value for dialogue area height parameter (toMovDialogueHeight), defaulting to 100.", isWarning=True)
            dialogueHeight = 100
        try:
            fontSize = int(mode.get(kDialogueFontSize))
        except ValueError, e:
            log("Could not get value for dialogue font size parameter (toMovDialogueFontSize), defaulting to 20.", isWarning=True)
            fontSize = 20

        # setup readNodes (and text nodes for the dialogue)
        for readFile in readNodes:
            filePath = self.repath.localize(readFile[kFilePath])
            # Read node pointing to the panel's jpeg
            readNode = nuke.createNode('Read')
            readNode["file"].setValue('%s' % filePath)
            # Reformat node to have extra height to fit the dialogue
            reformatNode = nuke.createNode('Reformat')
            reformatNode["type"].setValue(1)
            reformatNode["box_fixed"].setValue(True)
            reformatNode["box_width"].setValue(readNode.width())
            reformatNode["box_height"].setValue(readNode.height() + dialogueHeight)
            reformatNode["black_outside"].setValue(True)
            # Transform node to have the dialogue space at the bottom
            transformNode = nuke.createNode('Transform')
            transformNode["translate"].setValue([0, dialogueHeight/2])
            # Text node containing the actual dialogue
            textNode = nuke.createNode('Text')
            textNode["font"].setValue(os.environ["FLIX_FOLDER"] + "/assets/SourceCodePro-Regular.ttf")
            textNode["size"].setValue(fontSize)
            textNode["box"].setValue([0, 0, readNode.width(), readNode.height()])
            # Justify dialogue center bottom
            textNode["xjustify"].setValue(1)
            textNode["yjustify"].setValue(3)
            textNode["message"].setValue('%s' % self.validateUnicodeChars(readFile[kDialogue]))

            readNodeList.append([textNode, readFile[kDuration]])

        # setup dissolveNode
        dissolveNode = nuke.createNode('Dissolve')
        dissolveNode['which'].setAnimated()
        for readNode in readNodeList:
            duration     = readNode[kDuration]
            animationKey = lastFrame + 1
            lastFrame    += duration
            dissolveNode.setInput(kInputNum, readNode[kReadNode])
            dissolveNode['which'].setValueAt(animationValue, animationKey)
            kInputNum      += 1
            animationValue += 1
            # skip the mask input
            if kInputNum == 2:
                kInputNum = 3

        # set dissolveNode animation curve to constant (step)
        dissolveNode.knobs()['which'].animations()[0].changeInterpolation(
            dissolveNode.knobs()['which'].animations()[0].keys(),
            nuke.CONSTANT)

        # create writeNode and set input to dissolve Node
        self.fileService.createFolders(os.path.dirname(destination))
        log("destination path is %s"%destination, isInfo=True)
        writeJpgNode = nuke.createNode('Write')
        writeJpgNode['name'].setValue('saveJPG')
        writeJpgNode["file"].fromUserText(self.repath.localize(destination))
        writeJpgNode.setInput(kInput1, dissolveNode)

        # setup root preferences
        nuke.root().knob("first_frame").setValue(1)
        nuke.root().knob("last_frame").setValue(lastFrame)
        nuke.root().knob("fps").setValue(frameRate)
        nuke.root().knob("format").setValue(flixFormat)

        # render then save the script
        nuke.scriptSave(scriptName)
        nuke.render(writeJpgNode, 1, int(lastFrame))
        log('Render Complete. %s' % self.repath.localize(source['scriptName']), isInfo=True)        