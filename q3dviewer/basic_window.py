#!/usr/bin/env python3

import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore
from PyQt5.QtWidgets import QWidget, QComboBox, QVBoxLayout, QSizePolicy,\
      QSpacerItem, QMainWindow
from OpenGL.GL import *
from PyQt5.QtGui import QKeyEvent, QVector3D, QMatrix4x4
from PyQt5.QtWidgets import QApplication, QWidget
import numpy as np
import signal
import sys
from PyQt5.QtWidgets import QLabel, QLineEdit, QDoubleSpinBox, QSpinBox
from q3dviewer.utils import *


class SettingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.combo_items = QComboBox()
        self.combo_items.currentIndexChanged.connect(self.onComboboxSelection)
        main_layout = QVBoxLayout()
        self.stretch = QSpacerItem(
            10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_layout.addWidget(self.combo_items)
        self.layout = QVBoxLayout()
        self.layout.addItem(self.stretch)
        main_layout.addLayout(self.layout)
        self.setLayout(main_layout)
        self.setWindowTitle("Setting Window")
        self.setGeometry(200, 200, 300, 200)
        self.items = {}

    def addSetting(self, name, item):
        self.items.update({name: item})
        self.combo_items.addItem("%s(%s)" % (name, item.__class__.__name__))

    def clearSetting(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def onComboboxSelection(self, index):
        self.layout.removeItem(self.stretch)
        # remove all setting of previous widget
        self.clearSetting()

        key = list(self.items.keys())
        try:
            item = self.items[key[index]]
            item.addSetting(self.layout)
            self.layout.addItem(self.stretch)
        except AttributeError:
            print("%s: No setting." % (item.__class__.__name__))


class ViewWidget(gl.GLViewWidget):
    def __init__(self):
        self.followed_name = 'none'
        self.named_items = {}
        self.color = '#000000'
        self.followable_item_name = ['none']
        self.active_keys = set()
        self.setting_window = SettingWindow()
        self.Twb = rpyxyz2mat(0, 0, 0, -0, -50, 20)
        self.Tbc = rpyxyz2mat(np.pi/3, 0, 0, 0, 0, 0)
        super(ViewWidget, self).__init__()

    def onFollowableSelection(self, index):
        self.followed_name = self.followable_item_name[index]

    def update(self):
        if self.followed_name != 'none':
            pos = self.named_items[self.followed_name].T[:3, 3]
            self.opts['center'] = QVector3D(pos[0], pos[1], pos[2])
        
        self.updateMovement()
        super().update()

    def addSetting(self, layout):
        label1 = QLabel("Set background color:")
        label1.setToolTip("using '#xxxxxx', i.e. #FF4500")
        box1 = QLineEdit()
        box1.setToolTip("'using '#xxxxxx', i.e. #FF4500")
        box1.setText(str(self.color))
        box1.textChanged.connect(self.setBKColor)
        layout.addWidget(label1)
        layout.addWidget(box1)
        label2 = QLabel("Set Focus:")
        combo2 = QComboBox()
        for name in self.followable_item_name:
            combo2.addItem(name)
        combo2.currentIndexChanged.connect(self.onFollowableSelection)
        layout.addWidget(label2)
        layout.addWidget(combo2)

    def setBKColor(self, color):
        if (type(color) != str):
            return
        if color.startswith("#"):
            try:
                self.setBackgroundColor(color)
                self.color = color
            except ValueError:
                return

    def addItem(self, name, item):
        self.named_items.update({name: item})
        if (item.__class__.__name__ == 'GLAxisItem'):
            self.followable_item_name.append(name)
        self.setting_window.addSetting(name, item)
        super().addItem(item)

    def mouseReleaseEvent(self, ev):
        if hasattr(self, 'mousePos'):
            delattr(self, 'mousePos')

    def mouseMoveEvent(self, ev):
        lpos = ev.localPos()
        if not hasattr(self, 'mousePos'):
            self.mousePos = lpos
        diff = lpos - self.mousePos
        self.mousePos = lpos
        if ev.buttons() == QtCore.Qt.MouseButton.RightButton:
            dR = rpy2mat(-diff.y() * 0.005, 0, 0)
            self.Tbc[:3, :3] = self.Tbc[:3, :3] @ dR
            dR = rpy2mat(0, 0, -diff.x() * 0.005)
            self.Twb[:3, :3] = self.Twb [:3, :3] @ dR
        elif ev.buttons() == QtCore.Qt.MouseButton.LeftButton:
            self.Twb[:3, 3] += self.Twb[:3, :3] @ np.array([-diff.x(), diff.y(), 0]) * 0.05



    def keyPressEvent(self, ev: QKeyEvent):
        if ev.key() == QtCore.Qt.Key_M:  # setting meun
            print("Open setting windows")
            self.openSettingWindow()
        if ev.key() == QtCore.Qt.Key_Up or  \
            ev.key() == QtCore.Qt.Key_Down or \
            ev.key() == QtCore.Qt.Key_Left or \
            ev.key() == QtCore.Qt.Key_Right or \
            ev.key() == QtCore.Qt.Key_Z or \
            ev.key() == QtCore.Qt.Key_X or \
            ev.key() == QtCore.Qt.Key_A or \
            ev.key() == QtCore.Qt.Key_D or \
            ev.key() == QtCore.Qt.Key_W or \
            ev.key() == QtCore.Qt.Key_S:
            self.active_keys.add(ev.key())
        else:
            super().keyPressEvent(ev)
        self.active_keys.add(ev.key())

    def keyReleaseEvent(self, ev: QKeyEvent):
        self.active_keys.discard(ev.key())

    def updateMovement(self):
        if self.active_keys == {}:
            return
        rotation_speed = 0.01
        translation_speed = 1
        z = np.abs(self.Twb[2, 3])
        if z < 20:
            translation_speed = z * 0.05
        if QtCore.Qt.Key_Up in self.active_keys:
            dR = rpy2mat(rotation_speed, 0, 0)
            self.Tbc[:3, :3] = self.Tbc[:3, :3] @ dR
        if QtCore.Qt.Key_Down in self.active_keys:
            dR = rpy2mat(-rotation_speed, 0, 0)
            self.Tbc[:3, :3] = self.Tbc[:3, :3] @ dR
        if QtCore.Qt.Key_Left in self.active_keys:
            dR = rpy2mat(0, 0, rotation_speed)
            self.Twb[:3, :3] = self.Twb [:3, :3]@ dR
        if QtCore.Qt.Key_Right in self.active_keys:
            dR = rpy2mat(0, 0, -rotation_speed)
            self.Twb[:3, :3] = self.Twb[:3, :3] @ dR
        if QtCore.Qt.Key_Z in self.active_keys:
            self.Twb[:3, 3] += self.Twb[:3, :3] @ self.Tbc[:3, :3] @ np.array([0, 0, +translation_speed])
        if QtCore.Qt.Key_X in self.active_keys:
            self.Twb[:3, 3] += self.Twb[:3, :3] @ self.Tbc[:3, :3] @ np.array([0, 0, -translation_speed])
        if QtCore.Qt.Key_A in self.active_keys:
            self.Twb[:3, 3] += self.Twb[:3, :3] @ np.array([-translation_speed, 0, 0])
        if QtCore.Qt.Key_D in self.active_keys:
            self.Twb[:3, 3] += self.Twb[:3, :3] @ np.array([translation_speed, 0, 0])
        if QtCore.Qt.Key_W in self.active_keys:
            self.Twb[:3, 3] += self.Twb[:3, :3] @ np.array([0, translation_speed, 0])
        if QtCore.Qt.Key_S in self.active_keys:
            self.Twb[:3, 3] += self.Twb[:3, :3] @ np.array([0, -translation_speed, 0])

    def wheelEvent(self, ev):
        delta = ev.angleDelta().x()
        if delta == 0:
            delta = ev.angleDelta().y()
        delta = delta * 0.03
        self.Twb[:3, 3] += self.Twb[:3, :3] @ self.Tbc[:3, :3] @ np.array([0, 0, -delta])
        self.update()

    def openSettingWindow(self):
        if self.setting_window.isVisible():
            self.setting_window.raise_()
        else:
            self.setting_window.show()

    def viewMatrix(self):
        return QMatrix4x4(np.linalg.inv(self.Twb @ self.Tbc).flatten())


class Viewer(QMainWindow):
    def __init__(self, name='Viewer', win_size=[1920, 1080], vw=ViewWidget):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        super(Viewer, self).__init__()
        self.vw = vw
        self.setGeometry(0, 0, win_size[0], win_size[1])
        self.initUI()
        self.setWindowTitle(name)

    def initUI(self):
        centerWidget = QWidget()
        self.setCentralWidget(centerWidget)
        layout = QVBoxLayout()
        centerWidget.setLayout(layout)
        self.viewerWidget = self.vw()
        layout.addWidget(self.viewerWidget, 1)
        timer = QtCore.QTimer(self)
        timer.setInterval(20)  # period, in milliseconds
        timer.timeout.connect(self.update)
        timer.start()

    def addItems(self, named_items: dict):
        for name, item in named_items.items():
            self.viewerWidget.addItem(name, item)

    def __getitem__(self, name: str):
        if name in self.viewerWidget.named_items:
            return self.viewerWidget.named_items[name]
        else:
            return None

    def update(self):
        # force update by timer
        self.viewerWidget.update()

    def closeEvent(self, _):
        sys.exit(0)

    def show(self):
        self.viewerWidget.setting_window.addSetting("main win", self.viewerWidget)
        super().show()
