import matplotlib.pyplot as plt
import numpy as np

import cv2


class ROIHelper:
    def __init__(self, video_path):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        self.frame = None

    def extract_sample_frames(self, num_frames=5):
        """Extract multiple sample frames to help identify ROI locations"""
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)

        for i, frame_idx in enumerate(frame_indices):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                filename = f"sample_frame_{i:02d}.jpg"
                cv2.imwrite(filename, frame)

        # Save a middle frame as reference (avoiding welcome screens)
        middle_frame_idx = total_frames // 2
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame_idx)
        ret, self.frame = self.cap.read()
        if ret:
            cv2.imwrite("reference_frame.jpg", self.frame)

    def analyze_frame_regions(self, frame_path="sample_frame_02.jpg"):
        """Analyze frame to help identify potential ROI regions"""
        frame = cv2.imread(frame_path)
        if frame is None:
            return

        # Create a grid overlay to help with coordinate selection
        plt.figure(figsize=(15, 10))
        plt.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        # Add grid lines every 100 pixels
        height, width = frame.shape[:2]
        for x in range(0, width, 100):
            plt.axvline(x=x, color="yellow", alpha=0.5, linewidth=0.5)
        for y in range(0, height, 100):
            plt.axhline(y=y, color="yellow", alpha=0.5, linewidth=0.5)

        # Add coordinate labels
        for x in range(0, width, 200):
            plt.text(x, 20, str(x), color="yellow", fontsize=8, weight="bold")
        for y in range(0, height, 200):
            plt.text(10, y, str(y), color="yellow", fontsize=8, weight="bold")

        plt.title("Frame with Grid Overlay - Use coordinates to define ROIs")
        plt.xlabel("X coordinate")
        plt.ylabel("Y coordinate")
        plt.savefig("frame_analysis.png", dpi=150, bbox_inches="tight")

    def test_roi_extraction(self, roi_coords, roi_name="test"):
        """Test ROI extraction with given coordinates"""
        if self.frame is None:
            # Use middle frame to avoid welcome screens
            total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            middle_frame_idx = total_frames // 2
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame_idx)
            ret, self.frame = self.cap.read()

        x, y, w, h = roi_coords
        height, width = self.frame.shape[:2]

        # Validate coordinates
        if x < 0 or y < 0 or x + w > width or y + h > height:
            return False

        # Extract and save ROI
        roi = self.frame[y : y + h, x : x + w]
        filename = f"roi_test_{roi_name}.jpg"
        cv2.imwrite(filename, roi)

        return True


def main():
    video_path = "/home/celia/FreelyMovingVR4Mice/dj_pipeline/vr4mice/videos/Nightingale_2024-08-14_1.mkv"

    helper = ROIHelper(video_path)

    # Extract sample frames
    helper.extract_sample_frames()

    # Analyze frame regions
    helper.analyze_frame_regions("sample_frame_02.jpg")

    # Test ROI coordinates
    test_rois = {"sync_signal": (1900, 560, 20, 20), "visual_input": (0, 570, 925, 510)}

    for roi_name, roi_coords in test_rois.items():
        helper.test_roi_extraction(roi_coords, roi_name)


if __name__ == "__main__":
    main()
