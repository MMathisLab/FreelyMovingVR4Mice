#from dlclivegui.camera import TISCam
import colorcet as cc
import os
from dlclivegui.camera.tiscamera_windows import TISCam
from dlclivegui.camera.tisgrabber_windows import TIS_CAM
from dlclivegui import camera
from dlclivegui import CameraPoseProcess
from dlclivegui.queue import ClearableMPQueue
from dlcProcessor import MyProcessor
import json
from pathlib import Path
import importlib
import time

import tkinter as tk
from tkinter import Tk, Toplevel, Button, Label
from PIL import Image, ImageTk, ImageDraw
from functools import partial
import multiprocess as mp


class FakeGUI:
    def __init__(self, cam_pose_proc, queue, parent=None, show_kpts=False):
        self.display_window = Toplevel(parent)
        if show_kpts:
            self.display_frame_label = Label(self.display_window)
            self.display_frame_label.pack()
        else:
            self.display_window = None
        self.cam_pose_proc = cam_pose_proc
        self.queue = queue
        all_colors = getattr(cc, 'fire')
        self.display_colors = all_colors[:: int(len(all_colors) / 50)]
        self.display_radius = 4
        self.display_lik_thresh = .3 

    def display_frame(self):
        
        if self.cam_pose_proc and self.display_window:

            frame = self.cam_pose_proc.get_display_frame()

            if frame is not None:
                img = Image.fromarray(frame)
                if frame.ndim == 3:
                    b, g, r = img.split()
                    img = Image.merge("RGB", (r, g, b))

                pose = self.cam_pose_proc.get_display_pose()
                if pose is not None:
                    pose = pose[0]
                    im_size = (frame.shape[1], frame.shape[0])
                    img_draw = ImageDraw.Draw(img)

                    for i in range(pose.shape[0]):
                        if pose[i, 2] > self.display_lik_thresh:
                            try:
                                x0 = (
                                    pose[i, 0] - self.display_radius
                                    if pose[i, 0] - self.display_radius > 0
                                    else 0
                                )
                                x1 = (
                                    pose[i, 0] + self.display_radius
                                    if pose[i, 0] + self.display_radius < im_size[1]
                                    else im_size[1]
                                )
                                y0 = (
                                    pose[i, 1] - self.display_radius
                                    if pose[i, 1] - self.display_radius > 0
                                    else 0
                                )
                                y1 = (
                                    pose[i, 1] + self.display_radius
                                    if pose[i, 1] + self.display_radius < im_size[0]
                                    else im_size[0]
                                )
                                coords = [x0, y0, x1, y1]
                                img_draw.ellipse(
                                    coords,
                                    fill=self.display_colors[i],
                                    outline=self.display_colors[i],
                                )
                            except Exception as e:
                                print(e)

                imgtk = ImageTk.PhotoImage(image=img)
                self.display_frame_label.imgtk = imgtk
                self.display_frame_label.configure(image=imgtk)

            self.display_frame_label.after(10, self.display_frame)

    def get_from_queue(self):
        data = self.queue.read(position='last', clear=False)
        print(data)


def spawn_camera(cam_tis=None, dlc_params=None, queue=None):
    if cam_tis is None:
        cam_tis = TISCam(
            serial_number= str(TIS_CAM().GetDevices()[0]), #"DMK 37BUX287"#
            resolution=[720, 540],
            exposure=0.005,
            crop=[220, 600, 40, 390],
        )
    
    if dlc_params is None:
        dlc_params = {
            "processor": {
                "object": partial(MyProcessor, queue),
            },
            "model_path": "C:/Users/Windows/Documents/Mathis_lab_code/FreelyMovingVR4Mice_aux/DLC_ma_supertopview5k_resnet_50_iteration-0_shuffle-1",
            "mode": "Optimize Rate",  # "Optimize Latency"
            "cropping": [0,600,0,400],
            "resize": 0.5,
        }

    print(dlc_params ["processor"])
    
    name = Path(r'C:\Users\Windows\Documents\DeepLabCut-live-GUI\config\AR_rig.json')
    fd = open(name)
    cfg = json.load(fd)
    fd.close()
    #print(this_cam)
    this_cam = cfg["cameras"]
    this_cam = this_cam["Imaging source"]
    #cam_type = this_cam["type"]

   
    #print(getattr(dlcProcessor, "MyProcessor"))

    dlc_proc_params = dlc_params["processor"]
    dlc_proc_params.update(cfg["processor_args"])
    print(dlc_proc_params)
    dlc_proc_params["processor_args"] = {"queue": None}
 
    dlc_params_ = cfg["dlc_options"]["model"].copy()
    dlc_params_["processor"] = dlc_proc_params

    cam_obj = getattr(camera, this_cam["type"])
    cam = cam_obj(**this_cam["params"])
    cam_pose_proc = CameraPoseProcess(cam)
    ret = cam_pose_proc.start_capture_process()

    cam_pose_proc.start_pose_process(dlc_params_)
    return cam_pose_proc
    
    #print(len(cam_pose_proc.display_pose_queue))

    #start_time = time.time()
    #if abs(start_time - time.time()) > 100:
    #    cam_pose_proc.stop_capture_process()
    #else:  
    #    print("CHECK POSES: " + str(cam_pose_proc.get_display_pose()))
  
if __name__ == '__main__': # and '__file__' in globals():
#print(TIS_CAM().GetDevices()[0])
    queue = ClearableMPQueue(maxsize=100)
    cam_pose_proc = spawn_camera(queue=queue)
    gui = FakeGUI(cam_pose_proc, queue, show_kpts=True)
    #proc = spawn_camera()
