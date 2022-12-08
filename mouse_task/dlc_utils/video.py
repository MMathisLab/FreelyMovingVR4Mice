import os
import cv2



class Video:
    def __init__(self, video_path):
        if not os.path.isfile(video_path):
            raise ValueError(f'Video path "{video_path}" does not point to a file.')

        self.path = video_path
        self.stream = cv2.VideoCapture(video_path)
        if not self.stream.isOpened():
            raise OSError("Video could not be opened.")

        self._n_frames = int(self.stream.get(cv2.CAP_PROP_FRAME_COUNT))
        self._width = int(self.stream.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._frame = cv2.UMat(self._height, self._width, cv2.CV_8UC3)

    def __len__(self):
        return self._n_frames

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def set_to_frame(self, ind):
        ind = min(ind, len(self) - 1)
        self.stream.set(cv2.CAP_PROP_POS_FRAMES, ind)

    def read_frame(self):
        self.stream.retrieve(self._frame)
        cv2.cvtColor(self._frame, cv2.COLOR_BGR2RGB, self._frame, 3)
        return self._frame.get()

    def close(self):
        self.stream.release()