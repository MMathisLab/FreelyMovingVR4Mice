"""Video Trimmer for Freely Moving VR4Mice
This script trims a video file to extract specific regions of interest (ROIs) defined by the user
in roi_helper.py. Then it detects session start and end frames based on visual input and sync signal ROIs,
and creates trimmed videos for both ROIs. It supports multiple trimming methods including direct cropping,
fast copy-based trimming, and OpenCV-based trimming as a fallback.
"""
import os

import numpy as np

import cv2

BLACK_THRESHOLD = 5  # Default threshold for detecting black pixels
CONSECUTIVE_FRAMES = 10
SESSION_START_BUFFER = 120  # Search buffer in seconds for session start detection

# NOTE(celia): all recordings are 120 fps (frame rate per second).


class VideoTrimmer:
    def __init__(self, input_video_path, output_video_path=None):
        """Initialize video trimmer

        Args:
            input_video_path: Path to input video file
            output_video_path: Path for output trimmed video (optional)
        """
        self.input_path = input_video_path
        self.output_path = output_video_path or self._generate_output_path()
        self.cap = cv2.VideoCapture(input_video_path)

        # Video properties
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"Input video: {self.input_path}")
        print(
            f"Video properties: {self.width}x{self.height}, {self.fps} fps, {self.total_frames} frames"
        )

        # Check frame rate against expected value
        # self.check_frame_rate(expected_fps=120.0)

    def _generate_output_path(self):
        """Generate output filename based on input filename"""
        base_name = os.path.splitext(self.input_path)[0]
        extension = os.path.splitext(self.input_path)[1]
        return f"{base_name}_trimmed{extension}"

    def _frame_to_time_str(self, frame_idx):
        """Convert frame index to time string (MM:SS.s format)"""
        seconds = frame_idx / self.fps
        minutes = int(seconds // 60)
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:05.2f}"

    def detect_session_frames_by_roi(
        self,
        visual_roi_coords,
        black_threshold=BLACK_THRESHOLD,
        sample_center_size=20,
        consecutive_frames=CONSECUTIVE_FRAMES,
    ):
        """
        Detect exact session frames by analyzing every frame in search regions

        Args:
            visual_roi_coords: (x, y, width, height) coordinates of visual input ROI
            black_threshold: Pixel intensity threshold - below this is considered "black" (welcome screen)
            sample_center_size: Size of center region to sample (e.g., 20x20 pixels)
            consecutive_frames: Number of consecutive "session" frames needed to confirm session start

        Returns:
            tuple: (session_start_frame, session_end_frame)
        """
        x, y, w, h = visual_roi_coords

        # Define center region coordinates within the ROI
        center_x = x + w // 2 - sample_center_size // 2
        center_y = y + h // 2 - sample_center_size // 2

        print(
            f"Analyzing visual ROI center region: ({center_x}, {center_y}, {sample_center_size}, {sample_center_size})"
        )
        print(
            f"Black threshold: {black_threshold} (below = welcome screen, above = session)"
        )

        # Calculate search ranges
        start_search_frame = int(
            SESSION_START_BUFFER * self.fps
        )  # Start from 10th second

        print(
            f"Searching for session start from frame {start_search_frame} ({self._frame_to_time_str(start_search_frame)})"
        )
        print(f"Searching for session end from last frame backwards")

        # Find session start: check every frame from 10th second onwards for consecutive session frames
        session_start = None
        consecutive_session_count = 0

        print("Searching for session start...")
        for frame_idx in range(start_search_frame, self.total_frames):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                # Extract center region of visual ROI
                center_region = frame[
                    center_y : center_y + sample_center_size,
                    center_x : center_x + sample_center_size,
                ]

                # Convert to grayscale and get mean intensity
                gray_center = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
                mean_intensity = np.mean(gray_center)

                if mean_intensity > black_threshold:
                    consecutive_session_count += 1
                    if consecutive_session_count >= consecutive_frames:
                        # Found sustained session activity, go back to find actual start
                        session_start = frame_idx - consecutive_frames + 1
                        print(
                            f"Session start found at frame {session_start} ({self._frame_to_time_str(session_start)})"
                        )
                        print(f"  Intensity at start: {mean_intensity:.1f}")
                        break
                else:
                    consecutive_session_count = 0

            # Progress update every 1000 frames
            if frame_idx % 1000 == 0:
                print(
                    f"  Checking frame {frame_idx} ({self._frame_to_time_str(frame_idx)})..."
                )

        if session_start is None:
            session_start = start_search_frame
            print(
                f"Warning: Could not detect session start, using frame {start_search_frame} ({self._frame_to_time_str(start_search_frame)})"
            )

        # Find session end: check every frame from end backwards until we find session content
        session_end = None

        print("Searching for session end...")
        for frame_idx in range(self.total_frames - 1, 0, -1):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                # Extract center region of visual ROI
                center_region = frame[
                    center_y : center_y + sample_center_size,
                    center_x : center_x + sample_center_size,
                ]

                # Convert to grayscale and get mean intensity
                gray_center = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
                mean_intensity = np.mean(gray_center)

                # If this frame is above threshold, it's session content - this is our end
                if mean_intensity > black_threshold:
                    session_end = frame_idx
                    print(
                        f"Session end found at frame {session_end} ({self._frame_to_time_str(session_end)})"
                    )
                    print(f"  Intensity at end: {mean_intensity:.1f}")
                    break

            # Progress update every 1000 frames
            if frame_idx % 1000 == 0:
                print(
                    f"  Checking frame {frame_idx} ({self._frame_to_time_str(frame_idx)})..."
                )

        if session_end is None:
            session_end = self.total_frames - int(
                10 * self.fps
            )  # 10 seconds before end
            print(
                f"Warning: Could not detect session end, using frame {session_end} ({self._frame_to_time_str(session_end)})"
            )

        # Ensure session_end is after session_start
        if session_end <= session_start:
            session_end = self.total_frames - int(5 * self.fps)  # 5 seconds before end
            print(
                f"Warning: Adjusted session end to frame {session_end} ({self._frame_to_time_str(session_end)})"
            )

        session_duration_sec = (session_end - session_start) / self.fps

        print(f"\nDetected session boundaries:")
        print(
            f"  Start frame: {session_start} ({self._frame_to_time_str(session_start)})"
        )
        print(f"  End frame: {session_end} ({self._frame_to_time_str(session_end)})")
        print(
            f"  Duration: {session_duration_sec:.1f}s ({session_end-session_start} frames)"
        )
        print(
            f"  Frames to remove: {session_start} (start) + {self.total_frames-session_end} (end)"
        )

        return session_start, session_end

    def save_validation_frames(
        self, session_start, session_end, visual_roi_coords, sample_center_size=20
    ):
        """Save key transition frames for manual validation of detection results"""
        x, y, w, h = visual_roi_coords

        # Calculate center region coordinates (same as in detection)
        center_x = x + w // 2 - sample_center_size // 2
        center_y = y + h // 2 - sample_center_size // 2

        print(f"\nSaving validation frames...")
        print(
            f"Center region being analyzed: ({center_x}, {center_y}, {sample_center_size}, {sample_center_size})"
        )

        # Key transition frames only
        validation_frames = [
            ("before_session_start", max(0, session_start - 1)),
            ("session_start", session_start),
            ("session_end", session_end),
            ("after_session_end", min(self.total_frames - 1, session_end + 1)),
        ]

        for frame_type, frame_idx in validation_frames:
            if 0 <= frame_idx < self.total_frames:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = self.cap.read()
                if ret:
                    # Save full frame with ROI and center region marked
                    full_frame_marked = frame.copy()

                    # Draw ROI rectangle in green
                    cv2.rectangle(
                        full_frame_marked, (x, y), (x + w, y + h), (0, 255, 0), 2
                    )

                    # Draw center region rectangle in red
                    cv2.rectangle(
                        full_frame_marked,
                        (center_x, center_y),
                        (center_x + sample_center_size, center_y + sample_center_size),
                        (0, 0, 255),
                        2,
                    )

                    # Add text labels
                    cv2.putText(
                        full_frame_marked,
                        "Visual ROI",
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2,
                    )
                    cv2.putText(
                        full_frame_marked,
                        "Center Region",
                        (center_x, center_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 255),
                        2,
                    )

                    cv2.imwrite(
                        f"validation_{frame_type}_frame{frame_idx}.jpg",
                        full_frame_marked,
                    )

                    # Calculate and print center region intensity
                    center_region = frame[
                        center_y : center_y + sample_center_size,
                        center_x : center_x + sample_center_size,
                    ]
                    gray_center = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
                    mean_intensity = np.mean(gray_center)

                    print(
                        f"  {frame_type}: frame {frame_idx} ({self._frame_to_time_str(frame_idx)}) - intensity = {mean_intensity:.1f}"
                    )

    def trim_video_to_rois(
        self, session_start, session_end, visual_roi_coords, sync_roi_coords
    ):
        """
        Direct crop and trim in one command using ffmpeg

        Args:
            session_start: First frame to include
            session_end: Last frame to include
            visual_roi_coords: (x, y, width, height) coordinates of visual input ROI
            sync_roi_coords: (x, y, width, height) coordinates of sync signal ROI
        """
        import subprocess

        print(
            f"\nTrimming video from frame {session_start} ({self._frame_to_time_str(session_start)}) to frame {session_end} ({self._frame_to_time_str(session_end)})..."
        )

        # Calculate time ranges
        start_time = session_start / self.fps
        duration = (session_end - session_start) / self.fps

        # Generate output paths
        base_name = os.path.splitext(self.input_path)[0]
        extension = os.path.splitext(self.input_path)[1]
        visual_output_path = f"{base_name}_visual_roi{extension}"
        sync_output_path = f"{base_name}_sync_roi{extension}"

        # Extract ROI coordinates
        visual_x, visual_y, visual_w, visual_h = visual_roi_coords
        sync_x, sync_y, sync_w, sync_h = sync_roi_coords

        print(f"Visual ROI: ({visual_x}, {visual_y}, {visual_w}, {visual_h})")
        print(f"Sync ROI: ({sync_x}, {sync_y}, {sync_w}, {sync_h})")

        try:
            # Process both ROIs in parallel using subprocess
            print("Processing both ROIs simultaneously...")

            # Visual ROI command
            visual_cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start_time),
                "-i",
                self.input_path,
                "-t",
                str(duration),
                "-filter:v",
                f"crop={visual_w}:{visual_h}:{visual_x}:{visual_y}",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                visual_output_path,
            ]

            # Sync ROI command
            sync_cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start_time),
                "-i",
                self.input_path,
                "-t",
                str(duration),
                "-filter:v",
                f"crop={sync_w}:{sync_h}:{sync_x}:{sync_y}",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                sync_output_path,
            ]

            # Run both commands in parallel
            process1 = subprocess.Popen(
                visual_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            process2 = subprocess.Popen(
                sync_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            # Wait for both to complete
            stdout1, stderr1 = process1.communicate()
            stdout2, stderr2 = process2.communicate()

            if process1.returncode != 0:
                print(f"Visual ROI error: {stderr1.decode()}")
                return False

            if process2.returncode != 0:
                print(f"Sync ROI error: {stderr2.decode()}")
                return False

            # Get output file sizes
            visual_size_mb = os.path.getsize(visual_output_path) / (1024 * 1024)
            sync_size_mb = os.path.getsize(sync_output_path) / (1024 * 1024)
            input_size_mb = os.path.getsize(self.input_path) / (1024 * 1024)

            print(f"\nTrimming completed!")
            print(f"  Input file: {input_size_mb:.1f} MB")
            print(
                f"  Visual ROI output: {visual_size_mb:.1f} MB - {visual_output_path}"
            )
            print(f"  Sync ROI output: {sync_size_mb:.1f} MB - {sync_output_path}")

            return True

        except Exception as e:
            print(f"Error: {e}")
            return False

    def auto_trim_video(
        self,
        visual_roi_coords,
        sync_roi_coords,
        black_threshold=BLACK_THRESHOLD,
        sample_center_size=20,
        validate=True,
    ):
        """
        Automatically detect and trim video to ROI regions
        """
        print("=== Automatic Video Trimming to ROIs ===")

        # Step 1: Detect session boundaries
        session_start, session_end = self.detect_session_frames_by_roi(
            visual_roi_coords,
            black_threshold=black_threshold,
            sample_center_size=sample_center_size,
        )

        # Step 2: Save validation frames if requested
        if validate:
            self.save_validation_frames(
                session_start, session_end, visual_roi_coords, sample_center_size
            )

        # Step 3: Trim video
        success = self.trim_video_to_rois(
            session_start, session_end, visual_roi_coords, sync_roi_coords
        )

        if not success:
            print("Trimming failed!")
            return None, None

        return session_start, session_end

    def __del__(self):
        """Clean up video capture"""
        if hasattr(self, "cap") and self.cap.isOpened():
            self.cap.release()

    def check_frame_rate(self, expected_fps=120.0, tolerance=0.1):
        """
        Check and validate the video frame rate

        Args:
            expected_fps: Expected frame rate (default: 120.0 fps)
            tolerance: Tolerance for frame rate comparison (default: 0.1 fps)

        Returns:
            bool: True if frame rate is within expected range, False otherwise
        """
        print(f"\n=== Frame Rate Check ===")

        # Get frame rate from video properties
        reported_fps = self.cap.get(cv2.CAP_PROP_FPS)

        # Calculate actual frame rate by measuring timestamp differences
        print("Measuring actual frame rate...")

        # Sample frames to calculate actual timing - check every 10th frame
        timestamps = []

        for i in range(0, self.total_frames, 10):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = self.cap.read()
            if ret:
                # Get timestamp in milliseconds
                timestamp_ms = self.cap.get(cv2.CAP_PROP_POS_MSEC)
                timestamps.append(timestamp_ms)

        # Calculate actual fps from timestamps
        if len(timestamps) > 1:
            time_diffs = np.diff(timestamps)  # Time differences in ms
            avg_time_diff = np.mean(time_diffs)  # Average time between sampled frames
            frame_interval = avg_time_diff / 10.0  # We sampled every 10th frame
            measured_fps = 1000.0 / frame_interval if frame_interval > 0 else 0
        else:
            measured_fps = 0
            print("Warning: Could not measure actual frame rate")

        # Alternative method: use total duration
        total_duration_ms = (
            self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
            / self.cap.get(cv2.CAP_PROP_FPS)
            * 1000
        )
        calculated_fps = (
            (self.total_frames / total_duration_ms) * 1000
            if total_duration_ms > 0
            else 0
        )

        print(f"Frame rate analysis:")
        print(f"  Reported FPS: {reported_fps:.3f}")
        print(f"  Measured FPS: {measured_fps:.3f}")
        print(f"  Calculated FPS: {calculated_fps:.3f}")
        print(f"  Expected FPS: {expected_fps:.3f}")

        # Check if within tolerance
        fps_diff_reported = abs(reported_fps - expected_fps)
        fps_diff_measured = (
            abs(measured_fps - expected_fps) if measured_fps > 0 else float("inf")
        )

        within_tolerance_reported = fps_diff_reported <= tolerance
        within_tolerance_measured = fps_diff_measured <= tolerance

        print(
            f"  Reported FPS difference: {fps_diff_reported:.3f} ({'✓' if within_tolerance_reported else '✗'})"
        )
        if measured_fps > 0:
            print(
                f"  Measured FPS difference: {fps_diff_measured:.3f} ({'✓' if within_tolerance_measured else '✗'})"
            )

        # Overall assessment
        if within_tolerance_reported:
            print(
                f"✓ Frame rate check PASSED - Video has expected frame rate of {expected_fps} fps"
            )
            return True
        else:
            print(
                f"⚠️ Frame rate check FAILED - Video frame rate ({reported_fps:.3f}) differs from expected ({expected_fps})"
            )
            print(f"  Difference: {fps_diff_reported:.3f} fps (tolerance: {tolerance})")

            # Provide recommendations
            if fps_diff_reported > 1.0:
                print("  Recommendation: Check if this is the correct video file")
            elif fps_diff_reported > tolerance:
                print("  Recommendation: Consider adjusting expected_fps or tolerance")

            return False

    def get_video_info(self):
        """
        Get comprehensive video information including frame rate details

        Returns:
            dict: Video information dictionary
        """
        # Get all available video properties
        properties = {
            "fps": self.cap.get(cv2.CAP_PROP_FPS),
            "total_frames": self.cap.get(cv2.CAP_PROP_FRAME_COUNT),
            "width": self.cap.get(cv2.CAP_PROP_FRAME_WIDTH),
            "height": self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
            "duration_sec": self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
            / self.cap.get(cv2.CAP_PROP_FPS),
            "fourcc": int(self.cap.get(cv2.CAP_PROP_FOURCC)),
            "format": self.cap.get(cv2.CAP_PROP_FORMAT),
            "mode": self.cap.get(cv2.CAP_PROP_MODE),
            "brightness": self.cap.get(cv2.CAP_PROP_BRIGHTNESS),
            "contrast": self.cap.get(cv2.CAP_PROP_CONTRAST),
            "saturation": self.cap.get(cv2.CAP_PROP_SATURATION),
            "hue": self.cap.get(cv2.CAP_PROP_HUE),
        }

        # Convert fourcc to readable format
        fourcc_str = "".join(
            [chr((int(properties["fourcc"]) >> 8 * i) & 0xFF) for i in range(4)]
        )
        properties["fourcc_str"] = fourcc_str

        print(f"\n=== Video Information ===")
        print(f"File: {self.input_path}")
        print(f"Dimensions: {int(properties['width'])}x{int(properties['height'])}")
        print(f"Frame rate: {properties['fps']:.3f} fps")
        print(f"Total frames: {int(properties['total_frames'])}")
        print(
            f"Duration: {properties['duration_sec']:.2f} seconds ({properties['duration_sec']/60:.1f} minutes)"
        )
        print(f"Codec (FourCC): {fourcc_str}")
        print(f"Format: {properties['format']}")

        return properties


def main():
    # Video path
    input_video = "/app/vr4mice/videos/full_videos_2/2025-07-18 15-58-26.mkv"

    # ROI coordinates for your setup -- obtained using the roi_helper.py script
    visual_roi = (0, 540, 960, 540)  # Bottom left quarter - visual input
    sync_roi = (1900, 540, 20, 20)  # Top right of bottom right quarter - sync signal

    # (1850,
    #     560,
    #     20,
    #     20,)
    
    # Create trimmer (this will automatically check frame rate)
    trimmer = VideoTrimmer(input_video)

    # Get comprehensive video information
    video_info = trimmer.get_video_info()

    # Auto-trim with validation - now saves two ROI videos
    session_start, session_end = trimmer.auto_trim_video(
        visual_roi,
        sync_roi,
        black_threshold=BLACK_THRESHOLD,
        sample_center_size=20,
        validate=True,
    )


if __name__ == "__main__":
    main()
