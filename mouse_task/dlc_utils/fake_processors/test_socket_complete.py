"""Complete socket communication test - tests sender and receiver together.

This script runs both the sender (server) and receiver (client) in parallel to test
complete socket communication including latency measurement.

Run from this directory:
    python test_socket_complete.py
"""

import sys
import time
import threading
from collections import deque
from typing import Dict, Optional
from pathlib import Path

import numpy as np
from multiprocessing.connection import Listener, Client, Connection
import pickle

# Add parent directory to path for relative imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from processor_with_signal import ProcessorWithSignal


class FakeTeensy:
    """Mock Teensy for testing without hardware."""

    def __init__(self, com: str = "COM3", baudrate: int = 9600):
        """Initialize fake Teensy that simulates photodiode readings."""
        self.com = com
        self.baudrate = baudrate
        self.reading_teensy = True
        self.input_data = deque()
        self.input_data_time = deque()

    def simulate_reading(self, signal_value: float, timestamp: float) -> None:
        """Simulate a photodiode reading based on the signal value."""
        noise = np.random.normal(0, 0.01)
        simulated_value = signal_value + noise
        self.input_data.append(simulated_value)
        self.input_data_time.append(timestamp)


class SocketSender(ProcessorWithSignal):
    """Socket sender - generates and sends signals."""

    def __init__(
        self,
        signal_delay: float = 1.0,
        signal_type: str = "pulse",
        freq: float = 5.0,
        num_frames: int = 100,
        use_teensy: bool = False,
        com: str = "COM3",
        baudrate: int = 9600,
        save_file_path: str = "latency_tests_results/",
    ):
        super().__init__(signal_delay=signal_delay, signal_type=signal_type, freq=freq)

        self.num_frames = num_frames
        self.curr_step = 0
        self.curr_time = self.start_time
        self.use_teensy = use_teensy
        self.save_file_path = save_file_path

        # Data storage
        self.time_stamp = deque()
        self.signal = deque()
        self.step = deque()

        # Socket setup
        self.address = ("localhost", 6000)
        self.listener: Optional[Listener] = None
        self.conn: Optional[Connection] = None

        # Test data for socket
        self.vals = np.array([0.0, -9.0, 0.59740335, 3.0])

        # Optional Teensy integration
        self.teensy = None
        self.use_fake_teensy = False
        if use_teensy:
            # Try real Teensy first, fall back to fake if hardware not available
            try:
                teensy_path = str(
                    Path(__file__).parent.parent.parent
                    / "latency_tests"
                    / "Teensy_latency"
                    / "TeensyLatency.py"
                )
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "TeensyLatency", teensy_path
                )
                teensy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(teensy_module)
                self.teensy = teensy_module.TeensyLatency(com, baudrate=baudrate)
            except Exception:
                self.teensy = FakeTeensy(com, baudrate)
                self.use_fake_teensy = True

    def start_server(self):
        """Start socket server and wait for connection."""
        self.listener = Listener(self.address, authkey=b"secret password")
        self.conn = self.listener.accept()

    def process(self) -> None:
        """Process one frame and send via socket."""
        self.curr_time = time.time()

        # Get signal
        self.curr_signal = self.get_signal(curr_time=self.curr_time)

        # Send via socket
        if self.conn:
            self.conn.send(
                [
                    self.curr_time,
                    np.sin(self.curr_time * 0.5) * 9,
                    self.vals[1],
                    self.vals[2],
                    self.vals[3],
                    self.curr_signal,
                ]
            )

        # Simulate fake Teensy reading if using fake
        if self.use_fake_teensy and self.teensy:
            self.teensy.simulate_reading(self.curr_signal, self.curr_time)

        # Store data
        self.time_stamp.append(self.curr_time)
        self.signal.append(self.curr_signal)
        self.step.append(self.curr_step)
        self.curr_step += 1

        # Sleep to simulate ~100Hz frame rate
        time.sleep(1 / 100)

    def run(self) -> Dict[str, np.ndarray]:
        """Run the sender for configured number of frames."""
        for i in range(self.num_frames):
            self.process()

        # Package results
        results = {
            "start_time": np.array(self.start_time),
            "time_stamp": np.array(self.time_stamp),
            "step": np.array(self.step),
            "signal": np.array(self.signal),
            "signal_type": self.signal_type,
            "signal_freq": self.signal_freq,
            "signal_delay": self.signal_delay,
        }

        # Add Teensy data if available
        if self.use_teensy and self.teensy:
            results["photodiode_read"] = np.array(self.teensy.input_data)
            results["photodiode_time"] = np.array(self.teensy.input_data_time)

        return results

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.use_teensy and self.teensy:
            self.teensy.reading_teensy = False

        if self.conn:
            self.conn.close()
        if self.listener:
            self.listener.close()


class SocketReceiver:
    """Receive and validate data."""

    def __init__(self, address=("localhost", 6000)):
        self.address = address
        self.reading = True
        self.input_data = deque()
        self.conn = None

    def connect(self):
        """Connect to the sender."""
        try:
            self.conn = Client(self.address, authkey=b"secret password")
            return True
        except ConnectionRefusedError:
            self.reading = False
            return False

    def read_on_thread(self):
        """Background thread to continuously read from socket."""
        while self.reading:
            try:
                this_read = self.conn.recv()
                rec_time = time.time()  # Record time immediately when received
                self.input_data.append((this_read, rec_time))
            except EOFError:
                self.reading = False
                break
            except Exception:
                self.reading = False
                break

    def start_receiving(self):
        """Start the background reading thread."""
        threading.Thread(target=self.read_on_thread, daemon=True).start()

    def read(self):
        """Read the next message from the buffer."""
        if len(self.input_data) >= 1:
            this_read, rec_time = self.input_data.popleft()  # Get in order, don't clear
            return {"time": rec_time, "vals": this_read}
        return None

    def run(self, duration: int = 10) -> Dict[str, np.ndarray]:
        """Run the receiver for specified duration."""
        time_from_send = deque()
        time_from_rec = deque()
        vals = deque()
        signals = deque()

        start_time = time.time()
        message_count = 0

        while (time.time() - start_time) < duration and self.reading:
            this_read = self.read()
            if this_read is not None:
                message = this_read["vals"]
                if len(message) >= 6:
                    time_from_send.append(message[0])
                    time_from_rec.append(this_read["time"])
                    vals.append(message[1:5])
                    signals.append(message[5])
                    message_count += 1
            else:
                time.sleep(1 / 200)  # Only sleep if no data available

        return {
            "send_time": np.array(time_from_send),
            "receive_time": np.array(time_from_rec),
            "vals": np.array(vals),
            "signals": np.array(signals),
        }

    def cleanup(self):
        """Clean up resources."""
        self.reading = False
        if self.conn:
            self.conn.close()


def test_socket_communication(
    signal_type: str = "pulse_geo",
    freq: float = 5.0,
    signal_delay: float = 1.0,
    num_frames: int = 1000,
    use_teensy: bool = False,
    save_results: bool = True,
    save_path: Optional[Path] = None,
) -> tuple:
    """Test complete socket communication with sender and receiver.

    Args:
        signal_type: Type of signal (pulse, pulse_geo, sin, flip)
        freq: Signal frequency in Hz
        signal_delay: Delay before signal starts (seconds)
        num_frames: Number of frames to send
        use_teensy: Whether to use Teensy (falls back to FakeTeensy if unavailable)
        save_results: Whether to save results to files

    Returns:
        tuple: (sender_results, receiver_results)
    """
    print("=" * 70)
    print(f"Testing Socket Communication")
    print("=" * 70)
    print(f"Signal: {signal_type} @ {freq} Hz, delay={signal_delay}s")
    print(f"Frames: {num_frames}")
    print(f"Teensy: {use_teensy}")
    print("=" * 70)

    # Create sender
    sender = SocketSender(
        signal_type=signal_type,
        freq=freq,
        signal_delay=signal_delay,
        num_frames=num_frames,
        use_teensy=use_teensy,
    )

    # Start server in background thread
    server_thread = threading.Thread(target=sender.start_server)
    server_thread.start()

    # Give server time to start
    time.sleep(1)

    # Create and connect receiver
    receiver = SocketReceiver()
    if not receiver.connect():
        print("\nERROR: Failed to connect receiver to sender")
        sender.cleanup()
        return None, None

    # Start receiver in background thread
    receiver.start_receiving()

    # Run sender (blocks until done)
    print("\nStarting data transmission...")
    sender_results = sender.run()

    # Give receiver time to catch up
    time.sleep(1)

    # Stop receiver
    receiver.cleanup()
    sender.cleanup()

    # Collect receiver results
    receiver_results = {"send_time": [], "receive_time": [], "vals": [], "signals": []}

    # Process any remaining data in receiver buffer
    while True:
        this_read = receiver.read()
        if this_read is None:
            break
        message = this_read["vals"]
        if len(message) >= 6:
            receiver_results["send_time"].append(message[0])
            receiver_results["receive_time"].append(this_read["time"])
            receiver_results["vals"].append(message[1:5])
            receiver_results["signals"].append(message[5])

    # Convert to numpy arrays
    for key in receiver_results:
        receiver_results[key] = np.array(receiver_results[key])

    # Calculate statistics
    print("\n" + "=" * 70)
    print("Results:")
    print("=" * 70)
    print(f"Sender: Generated {len(sender_results['signal'])} signals")
    print(f"Receiver: Received {len(receiver_results['receive_time'])} messages")

    # Assertions and validation
    signal_array = sender_results["signal"]
    assert (
        len(signal_array) == num_frames
    ), f"Expected {num_frames} frames, got {len(signal_array)}"
    assert (
        np.min(signal_array) >= 0.0 and np.max(signal_array) <= 1.0
    ), f"Signal out of range [0, 1]"

    # Signal-type specific validations
    if signal_type == "pulse" or signal_type == "pulse_geo":
        unique_vals = np.unique(np.round(signal_array, 2))
        assert (
            len(unique_vals) <= 3
        ), f"Pulse signal has too many unique values: {unique_vals}"
        print(f"  ✓ Valid pulse signal")
    elif signal_type == "sin":
        assert (
            np.min(signal_array) >= 0.0
        ), f"Sin signal below 0, got min={np.min(signal_array)}"
        assert (
            np.max(signal_array) <= 1.0
        ), f"Sin signal above 1, got max={np.max(signal_array)}"
        print(f"  ✓ Valid sin signal")
    elif signal_type == "flip":
        unique_vals = np.unique(signal_array)
        assert (
            len(unique_vals) == 2
        ), f"Flip signal should have exactly 2 unique values, got {unique_vals}"
        assert set(unique_vals) == {
            0.0,
            1.0,
        }, f"Flip signal should only be 0 or 1, got {unique_vals}"
        print(f"  ✓ Valid flip signal")

    if len(receiver_results["receive_time"]) > 0:
        latency = receiver_results["receive_time"] - receiver_results["send_time"]
        print(f"\nLatency Statistics:")
        print(f"  Mean: {np.mean(latency)*1000:.2f} ms")
        print(f"  Std:  {np.std(latency)*1000:.2f} ms")
        print(f"  Min:  {np.min(latency)*1000:.2f} ms")
        print(f"  Max:  {np.max(latency)*1000:.2f} ms")
        assert np.mean(latency) < 0.1, f"Mean latency too high: {np.mean(latency)}"
        print(f"  ✓ Latency acceptable (<100ms)")

        # Sent signal validation
        print(f"\nSent Signal Statistics:")
        print(f"  Range: [{np.min(signal_array):.3f}, {np.max(signal_array):.3f}]")
        print(f"  Mean:  {np.mean(signal_array):.3f}")

        # Validate received signals match sent signals (approximately)
        received_signals = receiver_results["signals"]
        if len(received_signals) > 0:
            # Validate received signal type
            if signal_type == "pulse" or signal_type == "pulse_geo":
                unique_vals = np.unique(np.round(received_signals, 2))
                assert (
                    len(unique_vals) <= 3
                ), f"Received pulse signal has too many unique values: {unique_vals}"
                print(f"  ✓ Received valid pulse signal")
            elif signal_type == "sin":
                assert (
                    np.min(received_signals) >= -0.05
                ), f"Received sin signal below 0, got min={np.min(received_signals)}"
                assert (
                    np.max(received_signals) <= 1.05
                ), f"Received sin signal above 1, got max={np.max(received_signals)}"
                print(f"  ✓ Received valid sin signal")
            elif signal_type == "flip":
                unique_vals = np.unique(received_signals)
                assert (
                    len(unique_vals) == 2
                ), f"Received flip signal should have exactly 2 unique values, got {unique_vals}"
                print(f"  ✓ Received valid flip signal")

            print(f"\nReceived Signal Statistics:")
            print(
                f"  Range: [{np.min(received_signals):.3f}, {np.max(received_signals):.3f}]"
            )
            print(f"  Mean:  {np.mean(received_signals):.3f}")

            # Check signal transmission accuracy
            if len(received_signals) > 0 and len(signal_array) > 0:
                # Match received signals to sent signals (they may not be in exact same order due to buffering)
                min_len = min(len(received_signals), len(signal_array))
                signal_diff = np.abs(
                    signal_array[-min_len:] - received_signals[-min_len:]
                )
                print(f"\nSignal Transmission Accuracy:")
                print(f"  Mean difference: {np.mean(signal_diff):.6f}")
                print(f"  Max difference: {np.max(signal_diff):.6f}")
                assert (
                    np.mean(signal_diff) < 0.02
                ), f"Signal transmission error too high: {np.mean(signal_diff)}"
                print(f"  ✓ Signal transmission accurate")

    # Save results
    if save_results:
        if save_path is None:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            save_path = Path("latency_tests_results") / f"socket_tests_{timestamp}"

        save_path.mkdir(exist_ok=True, parents=True)

        sender_file = (
            save_path / f"socket_sender_{signal_type}_{freq}hz_d{signal_delay}.npy"
        )
        receiver_file = (
            save_path / f"socket_receiver_{signal_type}_{freq}hz_d{signal_delay}.pickle"
        )

        np.save(sender_file, sender_results, allow_pickle=True)
        with open(receiver_file, "wb") as f:
            pickle.dump(receiver_results, f)

        print(f"  Saved to {save_path.name}/")

    print("=" * 70)

    return sender_results, receiver_results


def main():
    """Run socket communication tests for all signal type/frequency/delay combinations."""
    from datetime import datetime

    print("\n" + "=" * 70)
    print("COMPLETE SOCKET COMMUNICATION TEST - ALL COMBINATIONS")
    print("=" * 70)

    # Create single save path for all tests in this run
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    save_path = Path("latency_tests_results") / f"socket_tests_{timestamp}"
    save_path.mkdir(exist_ok=True, parents=True)
    print(f"Saving all results to: {save_path}\n")

    # Test all combinations
    signal_types = ["pulse", "pulse_geo", "sin", "flip"]
    frequencies = [3.0, 5.0, 10.0]
    delays = [0.5, 2.0]
    use_teensy_options = [True, False]

    all_results = []
    passed = 0
    failed = 0

    for use_teensy in use_teensy_options:
        teensy_label = "WITH Teensy" if use_teensy else "WITHOUT Teensy"
        print(f"\n{'#' * 70}")
        print(f"# Testing {teensy_label}")
        print(f"{'#' * 70}")

        for signal_type in signal_types:
            print(f"\n### Signal Type: {signal_type} ###")

            for freq in frequencies:
                for delay in delays:
                    try:
                        sender_results, receiver_results = test_socket_communication(
                            signal_type=signal_type,
                            freq=freq,
                            signal_delay=delay,
                            num_frames=100,
                            use_teensy=use_teensy,
                            save_results=True,
                            save_path=save_path,
                        )

                        if sender_results is not None:
                            all_results.append(
                                {
                                    "signal_type": signal_type,
                                    "freq": freq,
                                    "delay": delay,
                                    "use_teensy": use_teensy,
                                    "sender": sender_results,
                                    "receiver": receiver_results,
                                }
                            )
                            passed += 1
                        else:
                            failed += 1
                            print("  ✗ Test failed")
                    except AssertionError as e:
                        failed += 1
                        print(f"  ✗ Assertion failed: {e}")
                    except Exception as e:
                        failed += 1
                        print(f"  ✗ Error: {e}")

                    time.sleep(0.5)  # Brief pause between tests

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total combinations tested: {len(all_results) + failed}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"\nSummary by configuration:")
    print(f"  Signal types: {len(signal_types)}")
    print(f"  Frequencies: {len(frequencies)}")
    print(f"  Delays: {len(delays)}")
    print(f"  Teensy options: {len(use_teensy_options)}")
    print(
        f"  Total combinations: {len(signal_types) * len(frequencies) * len(delays) * len(use_teensy_options)}"
    )
    print("=" * 70)


if __name__ == "__main__":
    # Run single test
    # test_socket_communication(signal_type="pulse_geo", freq=5.0, signal_delay=1.0, num_frames=500, use_teensy=True)

    # Or run all tests
    main()
