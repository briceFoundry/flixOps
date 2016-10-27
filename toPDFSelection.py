#------------------------------------------------------------------------------
# toPDFSelection.py -
#------------------------------------------------------------------------------
# Copyright (c) 2015 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

from reportlab.lib.utils import ImageReader, simpleSplit
import reportlab.lib.pagesizes
import reportlab.pdfgen.canvas

import flix.fileServices
import flix.fileServices.fileLocal
import flix.plugins.pluginDecorator
import flix.core2.mode
import flix.plugins.toPDF
import flix.utilities.pdfTemplate

from flix.utilities.log import log as log
from flix.core2.shotCutList import ShotCutList

class ToPDFSelection(flix.plugins.toPDF.ToPDF9):
    def __init__(self):
        self.fileService = flix.fileServices.FileService()
        self.repath  = flix.fileServices.Repath()
        self.fileServiceLocal = flix.fileServices.fileLocal.FileLocal()

        # load the icon
        iconPath = flix.core2.mode.Mode().get('[FLIX_FOLDER]')+'/assets/20px-pdf_9.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label='Landscape Selection 9/pg',
                  icon=icon,
                  tooltip='Export Selected panels to PDF',
                  group='PDF',
                  pluginPath='flixConfig.plugins.toPDFSelection.ToPDFSelection')

    def execute(self, shotCutList, selection, additionalData=None):
        selectionList = []
        for i in selection:
          selectionList.append(shotCutList[i])
        self.newShots = []
        if additionalData is not None:
            self.newShots = additionalData.get('newShots', [])
        import flix.utilities.pdfTemplate
        flix.utilities.log.log(self.newShots)
        # Construct a new shotCutList with only the selected panels
        self.shotCutList = ShotCutList(show=shotCutList.show,
          sequence=shotCutList.sequence,
          branch=shotCutList.branch,
          version=shotCutList.version,
          user=shotCutList.user,
          shots=selectionList)
        self.addProgress(len(self.shotCutList)+8)
        self.mode = self.shotCutList.mode
        pdf = self.getPDFTemplate()

        pdf.buildCanvas()
        self.openPDF(pdf.output)
        self.removeProgress(1)
        if pdf._dialogueErrors:
            failedDialogues = ", ".join([shot.recipe.getLabelName() for shot in pdf._dialogueErrors])
            self._execMessage = "Executed %s Plugin Successfully\n\nFailed to parse dialogue for the following clips:\n%s"%(self.label, failedDialogues)

    def getPDFTemplate(self):
        pdf = PdfTemplateSelection(self.shotCutList, self.newShots)
        pdf.row = 3
        pdf.column = 3
        return pdf

# Overriding the buildCanvas method for the PdfTemplateSelection class *just* so that it can write over the existing PDF, should there be one.
class PdfTemplateSelection(flix.utilities.pdfTemplate.PdfTemplate):
    def buildCanvas(self):
        """
        Builds a canvas object with current settings
        :return: canvas object
        """
        # get output. if a PDF already exists for this version, override it because the selection could be different
        self.getOutput()

        # get page width and height
        self.pageWidth, self.pageHeight = self.getPageSize()

        # create an empty canvas
        self.canvas = reportlab.pdfgen.canvas.Canvas(self.repath.localize(self.output), pagesize=self.pageSize)

        rowCounter = 0
        colCounter = 0
        pageNumber = 1
        self.panelVertShift = 0
        self.textGap = max(1, int(self.shotCutList.mode['[pdfDialogueGap]']))
        self.header  = self.marginSize*1.5

        # set the font type from parameters
        self.loadFontType()

        # set the canvas settings
        self.setCanvasSettings(pageNumber)

        # loop through imageDataList and create the pages of PDF with all content based on row and column count provided
        for index, imageData in enumerate(self.imageDataList):
            image = imageData['path']
            self.fileService.copyToLocal(image)
            if not self.fileServiceLocal.exists(image):
                image = self.mode.get('[FLIX_FOLDER]')+'/assets/errorImageInverted.jpg'
            panel = ImageReader(image)

            # figure out the image sizes based on the number of row's and column's
            panelWidth, panelHeight = self.getPanelSize(panel)

            # get each panels XY position on the pdf page
            panelX, panelY = self.getPanelPosition(panelWidth, panelHeight, rowCounter, colCounter)

            imageData.update({"panelX":panelX,
                              "panelY":panelY,
                              "panelW":panelWidth,
                              "panelH":panelHeight})

            # insert the image and stroke
            self.canvas.drawImage(panel, panelX, panelY, width=panelWidth, height=panelHeight)
            self.canvas.rect(panelX, panelY, width=panelWidth, height=panelHeight)

            # insert panel label and dialogue
            self.setPanelDialogueData(imageData)

            # set index number of each panel
            indexY = panelY - 10
            indexX = panelX + panelWidth
            self.canvas.setFillColor(self.fontColor)
            self.canvas.drawRightString(indexX, indexY, str(index+1))

            # check if shot status exists and set icon
            self.setPanelShotStatus(imageData)

            # check if the current panel is new and set new icon
            self.setPanelNewIcon(imageData)

            # set the shot label
            self.setPanelShotLabel(imageData)

            # check the row's and column's counter to set the next image in the correct place
            colCounter += 1
            if colCounter == self.column:
                colCounter = 0
                rowCounter += 1

            if rowCounter == self.row and not index == (len(self.imageDataList)-1):
                self.setWatermark()
                self.canvas.showPage()
                pageNumber += 1
                self.setCanvasSettings(pageNumber)
                rowCounter = 0
            elif index == (len(self.imageDataList)-1):
                self.setWatermark()
            self.serverSession.processingRemove(1)

        # save the pdf
        self.canvas.save()
        self.serverSession.processingRemove(1)
        return self.canvas
