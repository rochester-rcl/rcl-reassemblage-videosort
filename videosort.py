import cv2
import sys
import numpy as np
import argparse
import os
from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5.QtMultimedia import QMediaPlaylist, QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt5.QtWidgets import QWidget, QApplication, QMainWindow, QFileDialog, QMessageBox, QListWidgetItem, QVBoxLayout, QGraphicsScene, QGraphicsView
from mainwindow import Ui_MainWindow
from threading import Thread


class VideoSortApp(QMainWindow, Ui_MainWindow, QWidget):

    def __init__(self):
        super(VideoSortApp, self).__init__()
        self.setupUi(self)
        self.filename = None
        self.directory = None
        self.sort.setEnabled(False)
        self.fileOpen.clicked.connect(self.fileDialog)
        self.dirOpen.clicked.connect(self.folderDialog)
        self.sort.clicked.connect(self.sortVideo)
        self.results.setViewMode(self.results.IconMode)
        self.results.setResizeMode(self.results.Adjust)
        self.features = None
        self.sorted = None

        #player properties
        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.playlist = QMediaPlaylist(self.player)
        self.videoItem = QGraphicsVideoItem()
        self.videoItem.setSize(QtCore.QSizeF(640, 480))
        scene = QGraphicsScene(self)
        scene.addItem(self.videoItem)
        self.graphicsView.setScene(scene)
        self.player.setVideoOutput(self.videoItem)
        self.graphicsView.resize(640,480)
        self.graphicsView.show()
        self.results.itemDoubleClicked.connect(self.seekVideo)

    def sizeHint(self):
        return QtCore.QSize(640,480)

    def fileDialog(self):
        dialog = QFileDialog()
        if dialog.getOpenFileName:
            self.filename = dialog.getOpenFileName()[0]
            self.sort.setEnabled(True)

    def folderDialog(self):
        dialog = QFileDialog()
        if dialog.getExistingDirectory:
            self.directory = dialog.getExistingDirectory()
            self.sort.setEnabled(True)

    def sortVideo(self):

        dialog = QFileDialog()
        folder = dialog.getExistingDirectory(self, 'Select output directory for thumbnail images')
        if folder:
            if self.filename:
                self.getThread = VideoSort(self.filename, folder, 'frame')
                #self.results.setIconSize(QtCore.QSize(self.getThread.thumbInfo['resolution'][0], self.getThread.thumbInfo['resolution'][1]))
                #slot
                self.getThread.resultsSignal.connect(self.setFeatures)
                self.getThread.start()
                self.player.setMedia(QMediaContent(QtCore.QUrl.fromLocalFile(self.filename)))
                self.currentMedia = self.filename

            if self.directory:
                formatList = ['.mp4', '.mov', '.mkv', '.avi']
                for dirname, dirnames, filenames in os.walk(self.directory):
                    supportedFiles = [os.path.abspath(os.path.join(dirname, path)) for path in filenames if os.path.splitext(path)[1] in formatList]

                for filename in supportedFiles:
                    self.getThread = VideoSort(filename, folder, os.path.splitext(filename.split('/')[-1])[0])
                    self.getThread.resultsSignal.connect(self.setFeatures)
                    self.getThread.start()
                    self.player.setMedia(QMediaContent(QtCore.QUrl.fromLocalFile(filename)))

    def setFeatures(self, features):
        #inherit QListWidgetItem and add some custom properties - i.e. the video and time in msec
        self.features = features
        self.hue.toggled.connect(self.displayResults)
        self.saturation.toggled.connect(self.displayResults)
        self.contours.toggled.connect(self.displayResults)

    def displayResults(self):
        self.results.clear()
        if self.hue.isChecked():
            sortedFeatures = sorted(self.features, key=lambda res: res['hue']['std'], reverse=False)
            self.sorted = True
        if self.saturation.isChecked():
            sortedFeatures = sorted(self.features, key=lambda res: res['sat']['std'], reverse=False)
            self.sorted = True
        if self.contours.isChecked():
            sortedFeatures = sorted(self.features, key=lambda res: res['contours']['area'], reverse=False)
            self.sorted = True

        if self.sorted:
            for feature in sortedFeatures:
                icon = QtGui.QIcon(feature['thumbnail'])
                item = VideoListItem(icon, feature)
                self.results.addItem(item)

    def seekVideo(self, Qitem):
        #Need to write a callback function to only seek once player is loaded - provide loading media graphic or progress bar
        self.player.stop()
        print self.player.mediaStatus()
        if Qitem.feature['video'] != self.currentMedia:
            self.player.setMedia(QMediaContent(QtCore.QUrl.fromLocalFile(Qitem.feature['video'])))
        self.player.setPosition(Qitem.feature['milliseconds'])
        self.player.play()


class VideoListItem(QListWidgetItem):
    def __init__(self, icon, feature):
        super(VideoListItem, self).__init__(icon, 'frame')
        self.feature = feature


class VideoSort(QtCore.QThread, QtCore.QObject):
    #design this to take a list of urls or single filename
    resultsSignal = QtCore.pyqtSignal(object)
    def __init__(self,inputFile, outPath, prefix):
        super(VideoSort, self).__init__()
        self.mediaObject = inputFile
        self.video = cv2.VideoCapture(inputFile)
        self.frames = int(self.video.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT))
        self.frameRate = self.video.get(cv2.cv.CV_CAP_PROP_FPS)
        self.features = []
        self.thumbInfo = {'resolution': \
                         (int(self.video.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH) / 4), \
                         int(self.video.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)/4)), \
                         'path': outPath, 'prefix': prefix }

    def run(self):
        sortedFeatures = self.getFeatures()
        self.resultsSignal.emit(sortedFeatures)

    def getFeatures(self):
        queryRate = 100
        queryFrame = int(self.frameRate * queryRate)
        i = queryFrame
        frameCount = 0
        while queryFrame < self.frames:

            self.video.set(cv2.cv.CV_CAP_PROP_POS_FRAMES, queryFrame)
            ret, frame = self.video.read()
            if ret == True:
                queryMilliseconds = (queryFrame / self.frameRate) * 1000
                thumbPath = self.saveThumb(frame, frameCount)
                res = {'video': self.mediaObject, 'milliseconds': queryMilliseconds, \
                      'frame': queryFrame, 'thumbnail': thumbPath}
                res['hue'] = self.computeHist(frame,0)
                res['sat'] =  self.computeHist(frame,1)
                res['contours'] = self.getContours(frame)
                print res
                self.features.append(res)
            else:
                self.video.release()
                break
            queryFrame += i
            frameCount += 1
        return self.features

    def computeHist(self,frame,channel):
        resultsHist = {}
        hsvFrame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsvFrame],[channel], None,[128],[0,256])
        hist = np.array(cv2.normalize(hist).flatten())
        resultsHist['mean'] = np.mean(hist)
        resultsHist['std'] = np.std(hist)
        return resultsHist

    def getContours(self, frame):
        resultsContours = {}
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray,30,570,apertureSize = 3)
        contours, h = cv2.findContours(edges,1,2)
        cArea = np.array([cv2.contourArea(contour) for contour in contours])
        resultsContours['area'] =  np.std(cArea)
        resultsContours['nContours'] = len(contours)
        return resultsContours

    def saveThumb(self, frame, frameCount):
        thumb = cv2.resize(frame, self.thumbInfo['resolution'], interpolation=cv2.INTER_AREA)
        output = "{}/{}{:d}.png".format(self.thumbInfo['path'],self.thumbInfo['prefix'],frameCount)
        cv2.imwrite(output, thumb)
        return output

if __name__ == "__main__":

    #Set up GUI
    calc = QApplication(sys.argv)
    window = VideoSortApp()
    window.setWindowTitle('Video Sorter')
    window.show()
    sys.exit(calc.exec_())
