import os, string
import unittest
import vtk, qt, ctk, slicer
import numpy as np
import SimpleITK as sitk
import sitkUtils

from slicer.ScriptedLoadableModule import *

#
# CompareVolumes
#

class CIP_CalciumScoring(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "CalciumScoring"
        parent.categories = ["CIP"]
        parent.dependencies = []
        parent.contributors = ["Alex Yarmarkovich"]  # replace with "Firstname Lastname (Org)"
        parent.helpText = """
    """
        parent.helpText = string.Template("""
    This module helps organize layouts and volume compositing to help compare images

Please refer to <a href=\"$a/Documentation/$b.$c/Modules/CalciumScoring\"> the documentation</a>.

    """).substitute({'a': parent.slicerWikiUrl, 'b': slicer.app.majorVersion, 'c': slicer.app.minorVersion})
        parent.acknowledgementText = """
    This file was originally developed by Alex Yarmarkovich.
    It was partially funded by NIH grant 9999999
"""  # replace with organization, grant and thanks.
        self.parent = parent

        # Add this test to the SelfTest module's list for discovery when the module
        # is created.  Since this module may be discovered before SelfTests itself,
        # create the list if it doesn't already exist.
    #     try:
    #         slicer.selfTests
    #     except AttributeError:
    #         slicer.selfTests = {}
    #     slicer.selfTests['CIP_CalciumScoring'] = self.runTest
    #
    # def runTest(self):
    #     tester = CIP_CalciumScoringTest()
    #     tester.runTest()
    #     print "runTest"


#
# qCIP_CalciumScoringWidget
#

class CIP_CalciumScoringWidget(ScriptedLoadableModuleWidget):
    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        settings = qt.QSettings()
        self.developerMode = settings.value('Developer/DeveloperMode').lower() == 'true'
        if not parent:
            self.parent = slicer.qMRMLWidget()
            self.parent.setLayout(qt.QVBoxLayout())
            self.parent.setMRMLScene(slicer.mrmlScene)
        else:
            self.parent = parent
        self.layout = self.parent.layout()
        if not parent:
            self.setup()
            self.parent.show()

        self.calcinationType = 0
        self.Threshold = 10.0
        self.croppedVolumeNode = slicer.vtkMRMLScalarVolumeNode()
        self.threshImage = vtk.vtkImageData()
        
    def setup(self):
        # Instantiate and connect widgets ...
        ScriptedLoadableModuleWidget.setup(self)

        #self.logic = CIP_CalciumScoringLogic()

        #
        # Parameters Area
        #
        parametersCollapsibleButton = ctk.ctkCollapsibleButton()
        parametersCollapsibleButton.text = "Parameters"
        self.layout.addWidget(parametersCollapsibleButton)

        # Layout within the dummy collapsible button
        parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

        #
        # target volume selector
        #
        self.inputSelector = slicer.qMRMLNodeComboBox()
        self.inputSelector.nodeTypes = ( ("vtkMRMLScalarVolumeNode"), "" )
        self.inputSelector.addEnabled = False
        self.inputSelector.removeEnabled = False
        self.inputSelector.noneEnabled = False
        self.inputSelector.showHidden = False
        self.inputSelector.showChildNodeTypes = False
        self.inputSelector.setMRMLScene( slicer.mrmlScene )
        self.inputSelector.setToolTip( "Pick the input to the algorithm." )
        parametersFormLayout.addRow("Target Volume: ", self.inputSelector)
        self.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onVolumeChanged)
        self.volumeNode = self.inputSelector.currentNode()
        
        #
        # Calcination type
        #
        self.calcinationTypeBox = qt.QComboBox()
        self.calcinationTypeBox.addItem("Heart")
        self.calcinationTypeBox.addItem("Aorta")
        parametersFormLayout.addRow("Calcination Region", self.calcinationTypeBox)
        self.calcinationTypeBox.connect("currentIndexChanged(int)", self.onTypeChanged)

        self.ThresholdSlider = ctk.ctkSliderWidget()
        #self.ThresholdSlider.setMinimum(-100)
        #self.ThresholdSlider.setMaximum(200)
        self.ThresholdSlider.setValue(self.Threshold)
        parametersFormLayout.addRow("Threshold Value", self.ThresholdSlider)
        self.ThresholdSlider.connect("valueChanged(double)", self.onThresholdChanged)

        #
        # ROI Area
        #
        self.roiCollapsibleButton = ctk.ctkCollapsibleButton()
        self.roiCollapsibleButton.text = "Heart ROI"
        self.layout.addWidget(self.roiCollapsibleButton)

        # Layout within the dummy collapsible button
        roiFormLayout = qt.QFormLayout(self.roiCollapsibleButton)

        #
        # ROI
        #
        self.ROIWidget = slicer.qMRMLAnnotationROIWidget()
        self.roiNode = slicer.vtkMRMLAnnotationROINode()
        slicer.mrmlScene.AddNode(self.roiNode)
        self.ROIWidget.setMRMLAnnotationROINode(self.roiNode)
        roiFormLayout.addRow("", self.ROIWidget)
        self.roiNode.AddObserver("ModifiedEvent", self.onROIChangedEvent, 1)

        # Add vertical spacer
        self.layout.addStretch(1)

        # Add temp nodes
        self.croppedNode=slicer.vtkMRMLScalarVolumeNode()
        self.croppedNode.SetHideFromEditors(1)
        slicer.mrmlScene.AddNode(self.croppedNode)
        self.connectedLabelsNode=slicer.vtkMRMLLabelMapVolumeNode()
        slicer.mrmlScene.AddNode(self.connectedLabelsNode)
        
        if self.inputSelector.currentNode():
            self.onVolumeChanged(self.inputSelector.currentNode())
            self.createModels()

    def onVolumeChanged(self, value):
        self.volumeNode = self.inputSelector.currentNode()
        if self.volumeNode != None: 
            xyz = [0,0,0]
            c=[0,0,0]
            slicer.vtkMRMLSliceLogic.GetVolumeRASBox(self.volumeNode,xyz,c)
            xyz[:]=[x*0.2 for x in xyz]
            self.roiNode.SetXYZ(c)
            self.roiNode.SetRadiusXYZ(xyz)
        self.createModels()

    def onTypeChanged(self, value):
        self.calcinationType = value
        if self.calcinationType == 0:
            self.roiCollapsibleButton.setEnabled(1)
            self.ROIWidget.setEnabled(1)
            self.roiNode.SetDisplayVisibility(1)
            #self.logic.cropVolumeWithROI(self.volumeNode, self.roiNode, self.croppedVolumeNode)
        else:
            self.roiCollapsibleButton.setEnabled(0)
            self.ROIWidget.setEnabled(0)
            self.roiNode.SetDisplayVisibility(0)
        self.createModels()

    def onThresholdChanged(self, value):
        self.Threshold = value
        self.createModels()

    def onROIChangedEvent(self, observee, event):
        self.createModels()

    def createModels(self):
        if self.calcinationType == 0 and self.volumeNode and self.roiNode:
            print 'in Heart Create Models'

            slicer.vtkSlicerCropVolumeLogic().CropVoxelBased(self.roiNode, self.volumeNode, self.croppedNode)
            cii= sitk.ReadImage( sitkUtils.GetSlicerITKReadWriteAddress(self.croppedNode.GetName()))
            ti=sitk.BinaryThreshold(cii,self.Threshold, 2000, 1, 0)
            cci=sitk.ConnectedComponent(ti, True)
            if cci.GetPixelID() != sitk.sitkInt16:
                cci = sitk.Cast( cci, sitk.sitkInt16 )
            sitk.WriteImage( cci, sitkUtils.GetSlicerITKReadWriteAddress(self.connectedLabelsNode.GetName()))
            #a = slicer.util.array(tn.GetID())
            #sa = sitk.GetImageFromArray(a)
        else:
            print "not implemented"


#
# CIP_CalciumScoringLogic
#

class CIP_CalciumScoringLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget
    """

    def __init__(self):
        self.cropVolumeLogic = slicer.vtkSlicerCropVolumeLogic()
        self.threshold = vtk.vtkImageThreshold()

    def cropVolumeWithROI(self, volumeNode, roiNode, croppedVolume):
        self.cropVolumeLogic.CropVoxelBased(roiNode, volumeNode, croppedVolume)
        #print croppedVolume

    def thresoldImage(self, inImage, value, threshImage):
        self.threshold.SetInputData(inImage)
        self.threshold.ThresholdByUpper(value)
        self.threshold.SetReplaceIn(1)
        self.threshold.SetReplaceOut(1)
        self.threshold.SetInValue(1)
        self.threshold.SetOutValue(0)
        self.threshold.Update()
        threshImage.DeepCopy(self.threshold.GetOutput())


class CIP_CalciumScoringTest(unittest.TestCase):
    """
    This is the test case for your scripted module.
    """

    def delayDisplay(self, message, msec=1000):
        """This utility method displays a small dialog and waits.
        This does two things: 1) it lets the event loop catch up
        to the state of the test so that rendering and widget updates
        have all taken place before the test continues and 2) it
        shows the user/developer/tester the state of the test
        so that we'll know when it breaks.
        """
        print(message)
        self.info = qt.QDialog()
        self.infoLayout = qt.QVBoxLayout()
        self.info.setLayout(self.infoLayout)
        self.label = qt.QLabel(message, self.info)
        self.infoLayout.addWidget(self.label)
        qt.QTimer.singleShot(msec, self.info.close)
        self.info.exec_()

    def setUp(self):
        """ Do whatever is needed to reset the state - typically a scene clear will be enough.
        """
        slicer.mrmlScene.Clear(0)
