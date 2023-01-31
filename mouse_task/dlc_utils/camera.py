from dlclivegui.camera import TISCam
from dlclivegui import CameraPoseProcess
from mouse_task.dlc_utils.dlcProcessor import MyProcessor


def spawn_camera(camera=None, dlc_params=None):
    if camera is None:
        camera = TISCam(
            serial_number="",
            resolution=[720, 540],
            exposure=0.005,
            crop=[220, 600, 40, 390],
        )

    if dlc_params is None:
        dlc_params = {
            "processor": {
                "object": MyProcessor,
            },
            "model_path": "path_to_model",
            "mode": "Optimize Rate",  # "Optimize Latency"
            "cropping": "",
            "resize": 0.5,
        }

    cam_pose_proc = CameraPoseProcess(camera)
    _ = cam_pose_proc.start_capture_process()
    cam_pose_proc.start_pose_process(dlc_params)
    cam_pose_proc.stop_capture_process()
