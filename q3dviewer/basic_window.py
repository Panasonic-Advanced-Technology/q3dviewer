#!/usr/bin/env python3

import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore
from PyQt5.QtWidgets import QWidget, QComboBox, QVBoxLayout, QSizePolicy,\
      QSpacerItem, QMainWindow
from OpenGL.GL import *
from PyQt5.QtGui import QKeyEvent, QVector3D
from PyQt5.QtWidgets import QApplication, QWidget
import numpy as np
import signal
import sys
from PyQt5.QtWidgets import QLabel, QLineEdit, QDoubleSpinBox, QSpinBox

from math import cos, radians, sin

from pyqtgraph import Vector

def rotation_matrix_from_elev_azim(elev, azim):
    Ry = np.array([
        [ np.cos(elev),  0, np.sin(elev)],
        [ 0, 1,  0],
        [ -np.sin(elev),0,  np.cos(elev)]
    ])
    Rz = np.array([
        [np.cos(azim), -np.sin(azim), 0],
        [np.sin(azim), np.cos(azim), 0],
        [0, 0, 1]
    ])
    rotation_matrix = Rz @ Ry 
    return rotation_matrix


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
            self.orbit(-diff.x(), diff.y())
        elif ev.buttons() == QtCore.Qt.MouseButton.LeftButton:
            pitch_abs = np.abs(self.opts['elevation'])
            camera_mode = 'view-upright'
            if(pitch_abs <= 45.0 or pitch_abs == 90):
                camera_mode = 'view'
            self.pan(diff.x(), diff.y(), 0, relative=camera_mode)

    def keyPressEvent(self, ev: QKeyEvent):
        if ev.key() == QtCore.Qt.Key_M:  # setting meun
            print("Open setting windows")
            self.openSettingWindow()
        if ev.key() == QtCore.Qt.Key_R:
            print("Clear viewer")
            for item in self.named_items.values():
                try:
                    item.clear()
                except:
                    pass
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
        rotation_speed = 0.5
        translation_speed = 0.2
        if QtCore.Qt.Key_Up in self.active_keys:
            self.opts['elevation'] += rotation_speed
        if QtCore.Qt.Key_Down in self.active_keys:
            self.opts['elevation'] -= rotation_speed
        if QtCore.Qt.Key_Left in self.active_keys:
            self.opts['azimuth'] += rotation_speed
        if QtCore.Qt.Key_Right in self.active_keys:
            self.opts['azimuth'] -= rotation_speed
        if QtCore.Qt.Key_Z in self.active_keys:
            elev = radians(self.opts['elevation'])
            azim = radians(self.opts['azimuth'])
            R = rotation_matrix_from_elev_azim(-elev, azim)
            p = R @ np.array([translation_speed, 0, 0])
            pos = Vector(p[0], p[1], p[2])
            self.opts['center'] -= pos
        if QtCore.Qt.Key_X in self.active_keys:
            elev = radians(self.opts['elevation'])
            azim = radians(self.opts['azimuth'])
            R = rotation_matrix_from_elev_azim(-elev, azim)
            p = R @ np.array([translation_speed, 0, 0])
            pos = Vector(p[0], p[1], p[2])
            self.opts['center'] += pos
        if QtCore.Qt.Key_A in self.active_keys:
            azim = radians(self.opts['azimuth'] + 90)
            pos = Vector(cos(azim), sin(azim), 0) * translation_speed
            self.opts['center'] -= pos
        if QtCore.Qt.Key_D in self.active_keys:
            azim = radians(self.opts['azimuth'] + 90)
            pos = Vector(cos(azim), sin(azim), 0) * translation_speed
            self.opts['center'] += pos
        if QtCore.Qt.Key_W in self.active_keys:
            azim = radians(self.opts['azimuth'])
            pos = Vector(cos(azim), sin(azim), 0) * translation_speed
            self.opts['center'] -= pos
        if QtCore.Qt.Key_S in self.active_keys:
            azim = radians(self.opts['azimuth'])
            pos = Vector(cos(azim), sin(azim), 0) * translation_speed
            self.opts['center'] += pos

    def wheelEvent(self, ev):
        delta = ev.angleDelta().x()
        if delta == 0:
            delta = ev.angleDelta().y()
        elev = radians(self.opts['elevation'])
        azim = radians(self.opts['azimuth'])
        R = rotation_matrix_from_elev_azim(-elev, azim)
        p = R @ np.array([delta *0.1, 0, 0])
        pos = Vector(p[0], p[1], p[2])
        self.opts['center'] -= pos
        self.update()

    def openSettingWindow(self):
        if self.setting_window.isVisible():
            self.setting_window.raise_()
        else:
            self.setting_window.show()


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
        self.viewerWidget.setCameraPosition(distance=40)
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
