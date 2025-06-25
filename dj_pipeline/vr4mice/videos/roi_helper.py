import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import matplotlib.patches as patches


class ROIHelper:
    def __init__(self, video_path):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        self.frame = None
        self.rois = {}

    def extract_sample_frames(self, num_frames=5):
        """Extract multiple sample frames to help identify ROI locations"""
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)

        for i, frame_idx in enumerate(frame_indices):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                filename = "sample_frame_{:02d}.jpg".format(i)
                cv2.imwrite(filename, frame)
                print("Saved {}".format(filename))

        # Also save a middle frame as reference (avoiding welcome screens)
        middle_frame_idx = total_frames // 2
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame_idx)
        ret, self.frame = self.cap.read()
        if ret:
            cv2.imwrite("reference_frame.jpg", self.frame)
            print("Saved reference_frame.jpg (middle frame)")

    def analyze_frame_regions(self, frame_path="sample_frame_02.jpg"):
        """Analyze frame to help identify potential sync signal regions"""
        frame = cv2.imread(frame_path)
        if frame is None:
            print("Could not load frame")
            return

        # Convert to grayscale for analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Create a grid overlay to help with coordinate selection
        plt.figure(figsize=(15, 10))
        plt.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        # Add grid lines every 100 pixels
        height, width = frame.shape[:2]
        print("Frame size: {}x{}".format(width, height))
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
        print("Saved frame_analysis.png with coordinate grid")

        # Analyze potential sync regions (corners and edges)
        self.analyze_corners(gray)

    def analyze_corners(self, gray_frame):
        """Analyze corners to find potential sync signal locations"""
        h, w = gray_frame.shape
        corner_size = 100  # Analyze 100x100 pixel corners

        corners = {
            "top_left": gray_frame[0:corner_size, 0:corner_size],
            "top_right": gray_frame[0:corner_size, w - corner_size : w],
            "bottom_left": gray_frame[h - corner_size : h, 0:corner_size],
            "bottom_right": gray_frame[h - corner_size : h, w - corner_size : w],
        }

        print("\nCorner Analysis (variance indicates potential sync regions):")
        for corner_name, corner_img in corners.items():
            variance = np.var(corner_img)
            mean_intensity = np.mean(corner_img)
            print(
                "{}: variance={:.2f}, mean_intensity={:.2f}".format(
                    corner_name, variance, mean_intensity
                )
            )

        # Find regions with high variance (potential sync signals)
        print("\nPotential sync signal regions (high variance):")
        for corner_name, corner_img in corners.items():
            if np.var(corner_img) > 1000:  # Threshold for high variance
                print("- {} might contain sync signal".format(corner_name))

    def create_roi_template(self):
        """Create a template for easy ROI specification"""
        template = """
# ROI Configuration Template
# Copy these coordinates and modify them based on your frame analysis

roi_configs = {
    # Sync signal ROI (small rectangle with alternating pixels)
    # Usually in corners - check frame_analysis.png
    'sync_signal': (x, y, width, height),
    
    # Visual input ROI (main display area for the mouse)
    # Usually the largest region showing experimental stimuli
    'visual_input': (x, y, width, height)
}

# Example coordinates based on common layouts:
# Top-left corner sync: (0, 0, 100, 100)
# Top-right corner sync: (width-100, 0, 100, 100)
# Bottom-left corner sync: (0, height-100, 100, 100)
# Bottom-right corner sync: (width-100, height-100, 100, 100)

# For visual input, typical values might be:
# Center region: (200, 150, 800, 600)
# Left region: (50, 100, 600, 500)
# Right region: (700, 100, 600, 500)
"""

        with open("roi_template.txt", "w") as f:
            f.write(template)
        print("Created roi_template.txt with coordinate examples")

    def test_roi_extraction(self, roi_coords, roi_name="test", use_middle_frame=True):
        """Test ROI extraction with given coordinates"""
        if self.frame is None or not use_middle_frame:
            # Use middle frame to avoid welcome screens
            total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            middle_frame_idx = total_frames // 2
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame_idx)
            ret, self.frame = self.cap.read()

        x, y, w, h = roi_coords
        height, width = self.frame.shape[:2]

        # Validate coordinates
        if x < 0 or y < 0 or x + w > width or y + h > height:
            print("Warning: ROI coordinates out of bounds!")
            print(
                "Frame size: {}x{}, ROI: x={}, y={}, w={}, h={}".format(
                    width, height, x, y, w, h
                )
            )
            return False

        # Extract ROI
        roi = self.frame[y : y + h, x : x + w]

        # Save ROI
        filename = "roi_test_{}.jpg".format(roi_name)
        cv2.imwrite(filename, roi)
        print("Saved {} - check if this looks correct".format(filename))

        # Analyze ROI
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        print(
            "ROI stats: mean={:.2f}, std={:.2f}, min={}, max={}".format(
                np.mean(gray_roi), np.std(gray_roi), np.min(gray_roi), np.max(gray_roi)
            )
        )

        return True

    def detect_session_boundaries(
        self, threshold_variance=1000, min_session_frames=1000
    ):
        """
        Automatically detect session start and end by analyzing frame variance
        Welcome screens typically have low variance (static), while sessions have higher variance
        """
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = self.cap.get(cv2.CAP_PROP_FPS)

        print(f"Analyzing {total_frames} frames to detect session boundaries...")
        print(f"Video FPS: {fps}")

        # Sample frames throughout the video to detect variance changes
        sample_interval = max(1, total_frames // 200)  # Sample ~200 frames
        frame_variances = []
        frame_indices = []

        for frame_idx in range(0, total_frames, sample_interval):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                # Convert to grayscale and calculate variance
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                variance = np.var(gray)
                frame_variances.append(variance)
                frame_indices.append(frame_idx)

        frame_variances = np.array(frame_variances)
        frame_indices = np.array(frame_indices)

        # Find session start: first sustained period of high variance
        session_start = None
        high_variance_count = 0
        for i, variance in enumerate(frame_variances):
            if variance > threshold_variance:
                high_variance_count += 1
                if high_variance_count >= 5:  # Need 5 consecutive high-variance samples
                    session_start = frame_indices[
                        i - 4
                    ]  # Go back to first high variance
                    break
            else:
                high_variance_count = 0

        # Find session end: last sustained period of high variance
        session_end = None
        high_variance_count = 0
        for i in range(len(frame_variances) - 1, -1, -1):
            if frame_variances[i] > threshold_variance:
                high_variance_count += 1
                if high_variance_count >= 5:  # Need 5 consecutive high-variance samples
                    session_end = frame_indices[
                        i + 4
                    ]  # Go forward to last high variance
                    break
            else:
                high_variance_count = 0

        # Fallback if detection fails
        if session_start is None:
            session_start = total_frames // 10  # Skip first 10%
            print("Warning: Could not detect session start, using 10% of video")

        if session_end is None:
            session_end = total_frames - (total_frames // 10)  # Skip last 10%
            print("Warning: Could not detect session end, using 90% of video")

        # Ensure minimum session length
        if session_end - session_start < min_session_frames:
            print(
                f"Warning: Detected session too short ({session_end - session_start} frames)"
            )
            session_start = total_frames // 10
            session_end = total_frames - (total_frames // 10)

        session_duration_sec = (session_end - session_start) / fps

        print(f"Session detected:")
        print(f"  Start frame: {session_start} ({session_start/fps:.1f}s)")
        print(f"  End frame: {session_end} ({session_end/fps:.1f}s)")
        print(
            f"  Duration: {session_duration_sec:.1f}s ({(session_end-session_start)} frames)"
        )

        return session_start, session_end

    def detect_session_by_roi_activity(
        self, roi_coords, threshold_change=50, window_size=10
    ):
        """
        Alternative method: detect session by monitoring activity in a specific ROI
        Useful if you know where the main content appears
        """
        x, y, w, h = roi_coords
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = self.cap.get(cv2.CAP_PROP_FPS)

        print(f"Analyzing ROI activity at ({x}, {y}, {w}, {h}) to detect session...")

        # Sample frames and extract ROI activity
        sample_interval = max(1, total_frames // 300)  # Sample ~300 frames
        roi_activities = []
        frame_indices = []

        prev_roi_mean = None
        for frame_idx in range(0, total_frames, sample_interval):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                # Extract ROI and calculate change from previous frame
                roi = frame[y : y + h, x : x + w]
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                roi_mean = np.mean(gray_roi)

                if prev_roi_mean is not None:
                    activity = abs(roi_mean - prev_roi_mean)
                else:
                    activity = 0

                roi_activities.append(activity)
                frame_indices.append(frame_idx)
                prev_roi_mean = roi_mean

        roi_activities = np.array(roi_activities)
        frame_indices = np.array(frame_indices)

        # Smooth the activity signal
        if len(roi_activities) >= window_size:
            smoothed = np.convolve(
                roi_activities, np.ones(window_size) / window_size, mode="same"
            )
        else:
            smoothed = roi_activities

        # Find sustained periods of high activity
        active_mask = smoothed > threshold_change

        # Find session start
        session_start = None
        for i in range(len(active_mask) - window_size):
            if (
                np.sum(active_mask[i : i + window_size]) >= window_size * 0.7
            ):  # 70% active
                session_start = frame_indices[i]
                break

        # Find session end
        session_end = None
        for i in range(len(active_mask) - window_size - 1, -1, -1):
            if (
                np.sum(active_mask[i : i + window_size]) >= window_size * 0.7
            ):  # 70% active
                session_end = frame_indices[i + window_size - 1]
                break

        # Fallback
        if session_start is None or session_end is None:
            print("ROI-based detection failed, falling back to variance method")
            return self.detect_session_boundaries()

        session_duration_sec = (session_end - session_start) / fps

        print(f"Session detected by ROI activity:")
        print(f"  Start frame: {session_start} ({session_start/fps:.1f}s)")
        print(f"  End frame: {session_end} ({session_end/fps:.1f}s)")
        print(f"  Duration: {session_duration_sec:.1f}s")

        return session_start, session_end

    def validate_session_boundaries(
        self, session_start, session_end, num_validation_frames=5
    ):
        """
        Validate detected boundaries by extracting sample frames
        """
        print("\nValidating session boundaries...")

        # Extract frames around session start
        for i, offset in enumerate([-100, -50, 0, 50, 100]):
            frame_idx = max(0, session_start + offset)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                filename = f"session_start_validation_{offset:+d}.jpg"
                cv2.imwrite(filename, frame)
                print(f"Saved {filename} (frame {frame_idx})")

        # Extract frames around session end
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        for i, offset in enumerate([-100, -50, 0, 50, 100]):
            frame_idx = min(total_frames - 1, session_end + offset)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                filename = f"session_end_validation_{offset:+d}.jpg"
                cv2.imwrite(filename, frame)
                print(f"Saved {filename} (frame {frame_idx})")

        print("Check validation images to verify session boundaries are correct")


def main():
    video_path = "/home/celia/FreelyMovingVR4Mice/dj_pipeline/vr4mice/videos/Nightingale_2024-08-14_1.mkv"

    helper = ROIHelper(video_path)

    print("Step 1: Extracting sample frames...")
    helper.extract_sample_frames()

    print(
        "Step 2: Analyzing frame regions (using sample_frame_02 to avoid welcome screens)..."
    )
    helper.analyze_frame_regions("sample_frame_02.jpg")

    print("\nStep 3: Creating ROI template...")
    helper.create_roi_template()

    print("\nStep 4: Test ROI coordinates (update these based on your analysis):")

    # Example ROI coordinates - UPDATE THESE BASED ON YOUR FRAME ANALYSIS
    test_rois = {"sync_signal": (1900, 560, 20, 20), "visual_input": (0, 570, 925, 510)}

    for roi_name, roi_coords in test_rois.items():
        print("\nTesting {} ROI with coordinates {}...".format(roi_name, roi_coords))
        helper.test_roi_extraction(roi_coords, roi_name)

    print("\nProcess complete! Check these files:")
    print("- sample_frame_XX.jpg: Different time points in your video")
    print(
        "- frame_analysis.png: sample_frame_02 with coordinate grid (avoids welcome screen)"
    )
    print("- roi_template.txt: Template for ROI coordinates")
    print("- roi_test_XX.jpg: Test extractions of your ROIs")

    print("\nNext steps:")
    print("1. Open frame_analysis.png to see coordinates (based on sample_frame_02)")
    print("2. Look at roi_test_XX.jpg to verify extractions")
    print("3. Update ROI coordinates in your main script")
    print("4. The analysis uses the middle frame to avoid welcome/end screens")


if __name__ == "__main__":
    main()
