#!/usr/bin/env python3

from sensor_msgs.msg import PointCloud2, Image, CameraInfo
from q3dviewer import *
import rospy
import numpy as np
import argparse
import cv2

viewer = None
cloud_accum = None
cloud_accum_color = None
clouds = []
remap_info = None
K = None


class CustomDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, decimals=4, *args, **kwargs):
        self.decimals = decimals
        super().__init__(*args, **kwargs)
        self.setDecimals(self.decimals)  # Set the number of decimal places

    def textFromValue(self, value):
        return f"{value:.{self.decimals}f}"

    def valueFromText(self, text):
        return float(text)


class ViewerWithPanel(Viewer):
    def __init__(self, **kwargs):
        self.xyz = np.array([0, 0, 0])
        self.rpy = np.array([0, 0, 0])
        self.Roc = np.array([[0, -1, 0],
                             [0, 0, -1],
                             [1, 0, 0]])
        self.Rol = self.Roc @ euler_to_matrix(self.rpy)
        self.psize = 2
        self.cloud_num = 1
        self.en_rgb = False
        super().__init__(**kwargs)

    def initUI(self):
        centerWidget = QWidget()
        self.setCentralWidget(centerWidget)
        main_layout = QHBoxLayout()
        centerWidget.setLayout(main_layout)

        # Create a vertical layout for the settings
        setting_layout = QVBoxLayout()

        # Add a checkbox for RGB
        self.checkbox_rgb = QCheckBox("Enable RGB Cloud")
        self.checkbox_rgb.setChecked(False)
        setting_layout.addWidget(self.checkbox_rgb)
        self.checkbox_rgb.stateChanged.connect(
            self.checkbox_changed)

        # Add XYZ spin boxes
        label_xyz = QLabel("Set XYZ:")
        setting_layout.addWidget(label_xyz)
        self.box_x = CustomDoubleSpinBox()
        self.box_x.setSingleStep(0.01)
        setting_layout.addWidget(self.box_x)
        self.box_y = CustomDoubleSpinBox()
        self.box_y.setSingleStep(0.01)
        setting_layout.addWidget(self.box_y)
        self.box_z = CustomDoubleSpinBox()
        self.box_z.setSingleStep(0.01)
        setting_layout.addWidget(self.box_z)
        self.box_x.setRange(-100.0, 100.0)
        self.box_y.setRange(-100.0, 100.0)
        self.box_y.setRange(-100.0, 100.0)

        # Add RPY spin boxes
        label_rpy = QLabel("Set Roll-Pitch-Yaw:")
        setting_layout.addWidget(label_rpy)
        self.box_roll = CustomDoubleSpinBox()
        self.box_roll.setSingleStep(0.01)
        setting_layout.addWidget(self.box_roll)
        self.box_pitch = CustomDoubleSpinBox()
        self.box_pitch.setSingleStep(0.01)
        setting_layout.addWidget(self.box_pitch)
        self.box_yaw = CustomDoubleSpinBox()
        self.box_yaw.setSingleStep(0.01)
        setting_layout.addWidget(self.box_yaw)
        self.box_roll.setRange(-np.pi, np.pi)
        self.box_pitch.setRange(-np.pi, np.pi)
        self.box_yaw.setRange(-np.pi, np.pi)

        label_psize = QLabel("Set point size:")
        setting_layout.addWidget(label_psize)
        self.box_psize = QSpinBox()
        self.box_psize.setValue(self.psize)
        self.box_psize.setRange(0, 5)
        self.box_psize.valueChanged.connect(self.update_psize)
        setting_layout.addWidget(self.box_psize)

        label_cloud_num = QLabel("Set cloud frame number:")
        setting_layout.addWidget(label_cloud_num)
        self.box_cloud_num = QSpinBox()
        self.box_cloud_num.setValue(self.cloud_num)
        self.box_cloud_num.setRange(1, 100)
        self.box_cloud_num.valueChanged.connect(self.update_cloud_num)
        setting_layout.addWidget(self.box_cloud_num)

        label_res = QLabel("The cam-lidar quat and translation:")
        setting_layout.addWidget(label_res)
        self.line_quat = QLineEdit()
        self.line_quat.setReadOnly(True)
        setting_layout.addWidget(self.line_quat)
        self.line_trans = QLineEdit()
        self.line_trans.setReadOnly(True)
        setting_layout.addWidget(self.line_trans)

        self.line_trans.setText(np.array2string(self.xyz, formatter={
                                'float_kind': lambda x: "%.4f" % x}, separator=', '))
        quat = matrix_to_quaternion(self.Rol)
        self.line_quat.setText(np.array2string(
            quat, formatter={'float_kind': lambda x: "%.4f" % x}, separator=', '))

        # Connect spin boxes to methods
        self.box_x.valueChanged.connect(self.update_xyz)
        self.box_y.valueChanged.connect(self.update_xyz)
        self.box_z.valueChanged.connect(self.update_xyz)
        self.box_roll.valueChanged.connect(self.update_rpy)
        self.box_pitch.valueChanged.connect(self.update_rpy)
        self.box_yaw.valueChanged.connect(self.update_rpy)

        # Add a stretch to push the widgets to the top
        setting_layout.addStretch(1)

        self.viewerWidget = self.vw()
        main_layout.addLayout(setting_layout)
        main_layout.addWidget(self.viewerWidget, 1)

        timer = QtCore.QTimer(self)
        timer.setInterval(20)  # period, in milliseconds
        timer.timeout.connect(self.update)
        self.viewerWidget.setCameraPosition(distance=5)
        self.viewerWidget.setBKColor('#ffffff')
        timer.start()

    def update_psize(self):
        self.psize = self.box_psize.value()

    def update_cloud_num(self):
        self.cloud_num = self.box_cloud_num.value()

    def update_xyz(self):
        x = self.box_x.value()
        y = self.box_y.value()
        z = self.box_z.value()
        self.xyz = np.array([x, y, z])
        self.line_trans.setText(np.array2string(self.xyz, formatter={
                                'float_kind': lambda x: "%.4f" % x}, separator=', '))

    def update_rpy(self):
        roll = self.box_roll.value()
        pitch = self.box_pitch.value()
        yaw = self.box_yaw.value()
        self.rpy = np.array([roll, pitch, yaw])
        self.Rol = self.Roc @ euler_to_matrix(self.rpy)
        quat = matrix_to_quaternion(self.Rol)
        self.line_quat.setText(np.array2string(
            quat, formatter={'float_kind': lambda x: "%.4f" % x}, separator=', '))

    def checkbox_changed(self, state):
        if state == QtCore.Qt.Checked:
            self.en_rgb = True
        else:
            self.en_rgb = False


def cameraInfoCB(data):
    global remap_info, K
    if remap_info is None:  # Initialize only once
        K = np.array(data.K).reshape(3, 3)
        D = np.array(data.D)
        rospy.loginfo("Camera intrinsic parameters set")
        height = data.height
        width = data.width
        mapx, mapy = cv2.initUndistortRectifyMap(
            K, D, None, K, (width, height), cv2.CV_32FC1)
        remap_info = [mapx, mapy]


def scanCB(data):
    global viewer, clouds, cloud_accum, cloud_accum_color
    pc = PointCloud.from_msg(data).pc_data
    data_type = viewer['scan'].data_type
    color = pc['intensity'].astype(np.uint32)
    cloud = np.rec.fromarrays(
        [np.stack([pc['x'], pc['y'], pc['z']], axis=1), color],
        dtype=data_type)
    while len(clouds) > viewer.cloud_num:
        clouds.pop(0)
    clouds.append(cloud)
    cloud_accum = np.concatenate(clouds)

    if cloud_accum_color is not None and viewer.en_rgb:
        viewer['scan'].setData(data=cloud_accum_color)
        viewer['scan'].setColorMode('RGB')
    else:
        viewer['scan'].setData(data=cloud_accum)
        viewer['scan'].setColorMode('I')


def draw_larger_points(image, points, colors, radius):
    for dx in range(-radius + 1, radius):
        for dy in range(-radius + 1, radius):
            distance = np.sqrt(dx**2 + dy**2)
            if distance <= radius:
                x_indices = points[:, 0] + dx
                y_indices = points[:, 1] + dy
                image[y_indices, x_indices] = colors
    return image


def imageCB(data):
    global cloud_accum, cloud_accum_color, remap_info, K
    if remap_info is None:
        rospy.logwarn("Camera parameters not yet received.")
        return

    image = np.frombuffer(data.data, dtype=np.uint8).reshape(
        data.height, data.width, -1)
    if data.encoding == 'bgr8':
        image = image[:, :, ::-1]  # convert BGR to RGB

    # Undistort the image
    image_un = cv2.remap(image, remap_info[0], remap_info[1], cv2.INTER_LINEAR)

    if cloud_accum is not None:
        cloud_local = cloud_accum.copy()
        tol = viewer.xyz
        Rol = viewer.Rol
        pl = cloud_local['xyz']
        po = (Rol @ pl.T + tol[:, np.newaxis]).T
        u = (K @ po.T).T
        u_mask = u[:, 2] != 0
        u = u[:, :2][u_mask] / u[:, 2][u_mask][:, np.newaxis]

        radius = viewer.psize  # Radius of the points to be drawn
        u = np.round(u).astype(np.int32)
        valid_x = (u[:, 0] >= radius) & (u[:, 0] < image_un.shape[1]-radius)
        valid_y = (u[:, 1] >= radius) & (u[:, 1] < image_un.shape[0]-radius)
        valid_points = valid_x & valid_y
        u = u[valid_points]

        intensity = cloud_local['color'][u_mask][valid_points]
        intensity_color = rainbow(intensity).astype(np.uint8)
        draw_image = image_un.copy()
        draw_image = draw_larger_points(draw_image, u, intensity_color, radius)
        rgb = image_un[u[:, 1], u[:, 0]]
        xyz = cloud_local['xyz'][u_mask][valid_points]
        color = (intensity.astype(np.uint32) << 24) | \
                (rgb[:, 0].astype(np.uint32) << 16) | \
                (rgb[:, 1].astype(np.uint32) << 8) | \
                (rgb[:, 2].astype(np.uint32) << 0)
        cloud_accum_color = np.rec.fromarrays(
            [xyz, color],
            dtype=viewer['scan'].data_type)
        viewer['img'].setData(data=draw_image)


def main():
    global viewer
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Configure topic names for LiDAR, image, and camera info.")
    parser.add_argument(
        '--lidar', type=str, default='lidar', help="Topic of LiDAR data")
    parser.add_argument('--camera', type=str, default='image_raw',
                        help="Topic of camera image data")
    parser.add_argument('--camera_info', type=str,
                        default='camera_info', help="Topic of camera info")
    args = parser.parse_args()

    app = QApplication([])
    viewer = ViewerWithPanel(name='Manual LiDAR Cam Calib')
    grid_item = GridItem(size=10, spacing=1, color=(0, 0, 0, 70))
    scan_item = CloudItem(size=2, alpha=1, color_mode='I')
    img_item = ImageItem(pos=np.array([0, 0]), size=np.array([800, 600]))
    viewer.addItems({'scan': scan_item, 'grid': grid_item, 'img': img_item})

    rospy.init_node('lidar_cam_manual_calib', anonymous=True)

    # Use topic names from arguments
    rospy.Subscriber(args.lidar, PointCloud2, scanCB, queue_size=1)
    rospy.Subscriber(args.camera, Image, imageCB, queue_size=1)
    rospy.Subscriber(args.camera_info, CameraInfo, cameraInfoCB, queue_size=1)

    viewer.show()
    app.exec_()


if __name__ == '__main__':
    main()
