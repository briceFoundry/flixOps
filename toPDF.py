#------------------------------------------------------------------------------
# toPDFShot.py -
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

class ToPDFShotsY(flix.plugins.toPDF.ToPDF9):
    def __init__(self):
        self.fileService = flix.fileServices.FileService()
        self.repath  = flix.fileServices.Repath()
        self.fileServiceLocal = flix.fileServices.fileLocal.FileLocal()

        # load the icon
        iconPath = flix.core2.mode.Mode().get('[FLIX_FOLDER]')+'/assets/20px-pdf_9.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label='Landscape Shots 9/pg ',
                  icon=icon,
                  tooltip='Export Sequence to PDF, with shot breaks per page',
                  group='PDF',
                  pluginPath='flixConfig.plugins.toPDF.ToPDFShotsY')


    def getPDFTemplate(self):
        pdf = PdfTemplatePerShot(self.shotCutList, self.newShots)
        pdf.row = 3
        pdf.column = 3
        return pdf



class PdfTemplatePerShot(flix.utilities.pdfTemplate.PdfTemplate):

    def buildCanvas(self):
        """
        Builds a canvas object with current settings
        :return: canvas object
        """
        # get output
        if self.getOutput():
            return

        # get page width and height
        self.pageWidth, self.pageHeight = self.getPageSize()

        # create an empty canvas
        self.canvas = reportlab.pdfgen.canvas.Canvas(self.repath.localize(self.output), pagesize=self.pageSize)

        rowCounter = 0
        colCounter = 0
        pageNumber = 1
        self.panelVertShift = 0
        self.textGap    = 50
        self.header = self.marginSize*1.5

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

            if imageData != self.imageDataList[-1]:
                if imageData['shotLabel'] != self.imageDataList[index+1]['shotLabel']:
                    shotChanged = True
                else:
                    shotChanged = False

            if (rowCounter == self.row and not index == (len(self.imageDataList)-1)) or shotChanged:
                self.setWatermark()
                self.canvas.showPage()
                pageNumber += 1
                self.setCanvasSettings(pageNumber)
                rowCounter = 0
                colCounter = 0
            elif index == (len(self.imageDataList)-1):
                self.setWatermark()
            self.serverSession.processingRemove(1)

        # save the pdf
        self.canvas.save()
        self.serverSession.processingRemove(1)
        return self.canvas
