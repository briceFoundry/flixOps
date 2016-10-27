#------------------------------------------------------------------------------
# toPDFShots.py -
#------------------------------------------------------------------------------
# Copyright (c) 2015 The Foundry Visionmongers Ltd.  All Rights Reserved.
#------------------------------------------------------------------------------

from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.colors import lightslategray, black, green, limegreen
import reportlab.lib.pagesizes
import reportlab.pdfgen.canvas


import flix.fileServices
import flix.fileServices.fileLocal
import flix.plugins.pluginDecorator
import flix.core2.mode
import flix.plugins.toPDF
import flix.utilities.pdfTemplate

from flix.core2.markerList           import MarkerList
import random
from flix.utilities.log               import log as log


class ToPDFShots(flix.plugins.toPDF.ToPDF9):
    def __init__(self):
        self.fileService = flix.fileServices.FileService()
        self.repath  = flix.fileServices.Repath()
        self.fileServiceLocal = flix.fileServices.fileLocal.FileLocal()

        # load the icon
        iconPath = flix.core2.mode.Mode().get('[FLIX_FOLDER]')+'/assets/20px-pdf_9.png'
        icon = self.fileService.loadByteArray(iconPath)

        self.init(label='Shots 12/pg ',
                  icon=icon,
                  tooltip='Export Shots to PDFs',
                  group='PDF',
                  pluginPath='flixConfig.plugins.toPDFShots.ToPDFShots')

    def execute(self, shotCutList, selection, additionalData=None):
        markerList = MarkerList.fromShotCutList(shotCutList)
        markerShotLists = MarkerList.markerShotCutList(shotCutList, markerList)
        for markerShot in markerShotLists:
            self.shotCutList = markerShot
            self.addProgress(len(self.shotCutList)+8)
            self.mode = self.shotCutList.mode
            pdf = self.getPDFTemplate()

            pdf.buildCanvas()
            self.removeProgress(1)
            if pdf._dialogueErrors:
                failedDialogues = ", ".join([shot.recipe.getLabelName() for shot in pdf._dialogueErrors])
                self._execMessage = "Executed %s Plugin Successfully\n\nFailed to parse dialogue for the following clips:\n%s"%(self.label, failedDialogues)

    def getPDFTemplate(self):
        pdf = PdfTemplatePerShot(self.shotCutList, [])
        pdf.row = 3
        pdf.column = 4
        return pdf


class PdfTemplatePerShot(flix.utilities.pdfTemplate.PdfTemplate):

    def getPageSize(self):
        """
        get the page width and height based on the layout of the page
        :return: width and height
        """
        tmpImport = __import__("reportlab.lib.pagesizes", globals(), locals(), ['letter'], -1)
        if self.pageOrientation  == "landscape":
            letter = getattr(tmpImport, 'elevenSeventeen')
            self.pageSize = getattr(tmpImport, self.pageOrientation)(letter)
        else:
            self.pageSize = getattr(tmpImport, self.pageOrientation)

        return self.pageSize[0], self.pageSize[1]

    def getOutput(self):
        """
        get the output file path and filename of pdf
        :return:
        """
        pdfNumLabel = self.row * self.column
        with self.mode.using({'pdfType':str(pdfNumLabel)}):
            self.output = self.mode.get('[sequencePDFFile]', self.shotCutList.getProperties())
        self.output = "".join([self.output.split('.pdf')[0], str(random.random()), '.pdf'])
        if self.fileService.exists(self.output):
            self.fileService.copyToLocal(self.output)
            return True

    def buildCanvas(self):
        """
        Builds a canvas object with current settings
        :return: canvas object
        """
        # get output
        if self.getOutput():
            return

        self.marginSize = 65

        # get page width and height
        self.pageWidth, self.pageHeight = self.getPageSize()

        # create an empty canvas
        self.canvas = reportlab.pdfgen.canvas.Canvas(self.repath.localize(self.output), pagesize=self.pageSize)

        rowCounter = 0
        colCounter = 0
        pageNumber = 1
        self.panelVertShift = 0
        self.textGap    = 120
        self.header = self.marginSize*1.5
        # self.header = 100
        log("self.header: %s" % self.header)

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

            # if imageData != self.imageDataList[-1]:
            #     if imageData['shotLabel'] != self.imageDataList[index+1]['shotLabel']:
            #         shotChanged = True
            #     else:
            #         shotChanged = False

            if (rowCounter == self.row and not index == (len(self.imageDataList)-1)):
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

    def getPanelSize(self, panel):
        """
        Calculate the width and height of each panel based on layout and row/column
        :param panel:
        :return:
        """
        if self.row >= self.column and not (self.row ==1 and self.column ==1):
            panelHeight = ((self.pageHeight-((self.marginSize*4)+self.textGap))/self.row) - (self.textGap*((self.row-1)/float(self.row)))
            panelWidth = panelHeight * (panel._width/float(panel._height) )
            if ((panelWidth*self.column)+(self.marginSize*(self.column+1))) >= self.pageWidth:
                panelWidth  = ((self.pageWidth-(self.marginSize*2))/self.column) - (self.marginSize*((self.column-1)/float(self.column)))
                panelHeight = panelWidth * (float(panel._height) / panel._width)
        else:
            panelWidth  = ((self.pageWidth-(self.marginSize*2))/self.column) - (self.marginSize*((self.column-1)/float(self.column)))
            panelHeight = panelWidth * (float(panel._height) / panel._width)

        return panelWidth, panelHeight

    def getPanelPosition(self, panelW, panelH, rowCounter, colCounter):
        """
        Calculate the XY position of the given panel, takes in consideration of panel size and number of row/column
        adds extra padding for dialogue and gaps between images for aesthetics
        :param panelW: panel width
        :param panelH: panel height
        :param rowCounter: the current row index
        :param colCounter: the current column index
        :return: panel XY positions as tuple
        """
        # calculate the gap between each image based on image size and page size
        self.imageGapW = ((self.pageWidth-(self.marginSize*2)) - (panelW * self.column))/(self.column-1) if self.column > 1 else 0
        self.imageGapH = ((self.pageHeight - ((self.header+self.marginSize)*2)) - (panelH * self.row))/self.row if self.row > 1 else 30

        # calculate where each images x,y positions are
        panelX =  ((panelW + self.imageGapW) * colCounter) + self.marginSize
        panelY =  ((self.pageHeight-(self.header+self.marginSize))  - ((panelH + self.imageGapH)*(rowCounter+1)))
        if rowCounter == 0:
            panelYExpected = ((self.pageHeight-(self.header+self.marginSize))  - (panelH*(rowCounter+1)))
            if panelY != panelYExpected:
                self.panelVertShift = panelY - panelYExpected
        panelY -= self.panelVertShift

        return panelX, panelY
        
    def setCompanyLogo(self):
        companyLogoWidth = 0
        if isinstance(self.companyLogo, ImageReader):
            logoWidth = float(self.companyLogo._width)
            logoHeight = float(self.companyLogo._height)
            companyLogoHeight = 50
            companyLogoWidth = companyLogoHeight * (logoWidth/logoHeight)
            logoX = self.marginSize - 20
            logoY = self.pageHeight - 60
            self.canvas.drawImage(self.companyLogo, logoX, logoY, width=companyLogoWidth, height=companyLogoHeight)
        return companyLogoWidth

    def setHeader(self):
        """
        sets all the header information per page, adds Title and tile bar, aligned on the top center of the page
        """
        companyLogoW = self.setCompanyLogo()
        companyLogoW += 5 if companyLogoW else 0 # add 5 for padding if company logo exists
        # set privacy info next to the company logo
        privacyInfo = {'msg1':"(c) Warner Bros. Entertainment Inc. This material is the",
                       'msg2':"property of Warner Bros. Animation. It is unpublished and",
                       'msg3':"must not be distributed, duplicated or used in any",
                       'msg4':"manner, except for production purposes, and may not be",
                       'msg5':"sold or transferred.",
                       'textColor':self.textColor,
                       'fontName':self.fontType,
                       'size':6}
        panelName = Paragraph('''<para align=center spaceb=3>
                                  <font name=%(fontName)s size=%(size)s color=%(textColor)s>%(msg1)s<br/>
                                  %(msg2)s<br/>%(msg3)s<br/>%(msg4)s<br/>%(msg5)s</font></para>''' % privacyInfo, self.styles['BodyText'])
        privacyTable = Table([[panelName]], colWidths=(self.pageWidth-(self.marginSize*2)))
        privacyTable.setStyle(TableStyle([('VALIGN',(-1,-1),(-1,-1),'TOP')]))
        privacyTable.wrapOn(self.canvas, self.marginSize, 10)
        privacyTable.drawOn(self.canvas, 250-self.pageWidth/2, self.pageHeight-70)

        # header text
        self.canvas.setFillColor("darkgreen")
        self.canvas.setFont(self.fontType, 50)
        self.canvas.drawString((self.pageWidth/2) - 55, self.pageHeight - 60, "GE&H")
        self.canvas.setFillColor("black")
        self.canvas.setFont(self.fontType, 15)
        self.canvas.drawString(100, self.pageHeight-100, "EP: 101               SQ: 02               SHOT: SH_0010                    LENGTH: 220")

    def setFooter(self, pageNumber):
        """
        sets all footer information per page, add page info, footer bar, and privacy info, aligned on the bottom center of the page
        :param pageNumber:
        :return:
        """
        # footer text
        self.canvas.setFont(self.fontType, 9)
        self.canvas.drawRightString(self.pageWidth/2, 10,"Page - %d" % pageNumber)

