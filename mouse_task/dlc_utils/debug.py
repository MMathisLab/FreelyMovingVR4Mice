        
from dlclivegui.camera.tiscamera_windows import TISCam
from dlclivegui import camera
from dlclivegui import CameraPoseProcess
from dlclivegui.queue import ClearableMPQueue
from dlcProcessor import MyProcessor
import json
from pathlib import Path
import importlib
import time
from dlclivegui.camera.tisgrabber_windows import TIS_CAM

if __name__ == '__main__':
    cam_tis = TISCam(
        serial_number= str(TIS_CAM().GetDevices()[0]), #"DMK 37BUX287"#
        resolution=[720, 540],
        exposure=0.005,
        crop=[220, 600, 40, 390],
    )

    name = Path(r'C:\Users\Windows\Documents\DeepLabCut-live-GUI\config\AR_rig.json')
    fd = open(name)
    cfg = json.load(fd)
    fd.close()
    #print(this_cam)
    this_cam = cfg["cameras"]
    this_cam = this_cam["Imaging source"]
    cam_obj = getattr(camera, this_cam["type"])
    cam = cam_obj(**this_cam["params"])
    cam_pose_proc = CameraPoseProcess(cam)
    ret = cam_pose_proc.start_capture_process()

    frames = []
    for _ in range(50):
        frames.append(cam_pose_proc.get_display_frame())
    import numpy as np
    assert np.array_equal(frames[0], frames[-1])