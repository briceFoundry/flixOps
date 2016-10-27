#------------------------------------------------------------------------------
# shotInfo.py
#------------------------------------------------------------------------------
# Copyright (c) 2015 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

from flix.core2.markerList            import MarkerList

from collections                      import OrderedDict


#------------------------------------------------------------------------------
# class
#------------------------------------------------------------------------------

class ShotInfo:

    #--------------------------------------------------------------------------
    # object
    #--------------------------------------------------------------------------

    def __init__(self, shotCutList):
        self.shotCutList  = shotCutList        

    #--------------------------------------------------------------------------
    # methods
    #--------------------------------------------------------------------------

    def getShotsInfo(self):
        markerList = MarkerList.fromShotCutList(self.shotCutList)
        shotLabels = []
        for marker in markerList:
            shotLabels.append(marker.name)
        markerShotLists = MarkerList.markerShotCutList(self.shotCutList, markerList)
        if not markerShotLists:
            markerShotLists.append(self.shotCutList)

        shots = []
        firstFrame = 1
        lastFrame = 0
        sequencePanelIndex = 0
        for markerShot in markerShotLists:
            if markerShot.isMarker:
                dialogue = ''
                shotInfo = OrderedDict()
                shotLabel = shotLabels[markerShotLists.index(markerShot)]
                shotInfo['shot label'] = shotLabel
                for shot in markerShot:
                    sequencePanelIndex += 1
                    duration = self.shotCutList[sequencePanelIndex].duration
                    lastFrame += int(round(duration))
                    if shot is markerShot[-1]:
                        dissolveOut = int(round(shot.dissolveOut))
                    if shot is markerShot[0]:
                        dissolveIn = int(round(shot.dissolveIn))
                    newDialogue = shot.recipe.getPoses()[0]['dialogue']
                    if newDialogue != '':
                        dialogue = '\n'.join([dialogue, newDialogue])
                workingDuration = (lastFrame + dissolveOut - firstFrame) + 1
                cutDuration = workingDuration - dissolveIn - dissolveOut
                shotInfo['first frame'] = firstFrame
                shotInfo['last frame'] = lastFrame + dissolveOut
                shotInfo['cut duration'] = cutDuration
                shotInfo['dissolve in'] = dissolveIn
                shotInfo['dissolve out'] = dissolveOut
                shotInfo['working duration'] = workingDuration
                shotInfo['dialogue'] = dialogue
                shots.append(shotInfo)
                firstFrame = lastFrame + 1 - dissolveOut
                sequencePanelIndex += 1
        return shots

