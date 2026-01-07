"""Base processor class with TTL signal generation capabilities."""

import time

import numpy as np

from dlclive import Processor


class ProcessorWithSignal(Processor):
    """Base DLC processor with configurable TTL signal generation.

    Supports multiple signal types:
    - "pulse": Periodic square wave at specified frequency
    - "pulse_geo": Periodic square wave with geometric jitter on each half-period
    - "sin": Low-amplitude sine wave
    - "flip": Toggle signal every frame
    """

    def __init__(
        self, signal_delay: float = 10, signal_type: str = "pulse_geo", freq: float = 5
    ) -> None:
        """
        Args:
            signal_delay: Initial delay (seconds) before signal starts
            signal_type: Type of signal to generate ("pulse", "pulse_geo", "sin", "flip")
            freq: Frequency in Hz for periodic signals
        """
        super().__init__()

        self.curr_signal: float = 0  # latest TTL value
        self.start_time: float = time.time()
        self.signal_type: str = signal_type
        self.signal_delay: float = signal_delay
        self.signal_freq: float = freq

        # State for periodic TTL with geometric jitter (pulse_geo)
        self.next_jitter_toggle: float = self.start_time + self.signal_delay

    def get_signal(self, curr_time: float) -> float:
        """Route to the appropriate signal generator based on ``signal_type``.

        Args:
            curr_time: Wall-clock time (seconds).
        """
        if curr_time is None:
            raise ValueError("curr_time is required")
        t = curr_time
        if self.signal_type == "pulse":
            return self.get_nhz_pulse(curr_time=t)
        elif self.signal_type == "sin":
            return self.get_sin_wave(curr_time=t)
        elif self.signal_type == "flip":
            return self.flip_every_frame(curr_time=t)
        elif self.signal_type == "pulse_geo":
            return self.get_nhz_pulse_jittered(curr_time=t)
        else:
            raise ValueError(f"Unknown signal_type: {self.signal_type}")

    def get_nhz_pulse(self, curr_time: float) -> float:
        """Generate periodic square wave at specified frequency.

        Args:
            curr_time: Current wall-clock time

        Returns:
            0 or 1 (TTL signal value)
        """
        if (curr_time - self.start_time) < self.signal_delay:
            curr_signal = 0
        else:
            # Square wave via sign of sine: mapped to {0,1}
            curr_signal = (np.sign(np.sin(self.signal_freq * np.pi * curr_time)) + 1) / 2
        return curr_signal

    def get_nhz_pulse_jittered(
        self,
        curr_time: float,
        max_extra: float = 0.5,
        base_unit: float = 0.005,
    ) -> float:
        """Generate non-periodic square wave with geometric jitter.

        Each half-period has a base duration of 1/(2*freq) plus a random
        geometric delay capped at max_extra.

        Args:
            curr_time: Current wall-clock time
            st: Start time (when recording began)
            freq: Target frequency in Hz (actual rate will be lower due to jitter)
            delay: Initial delay before signal starts
            max_extra: Maximum additional jitter per half-period (seconds)
            base_unit: Time resolution for geometric distribution (seconds)

        Returns:
            0 or 1 (TTL signal value)

        Note:
            At default freq=5Hz: half-period=100ms, mean jitter~50ms, capped at 500ms,
            giving an effective rate of ~4Hz.
        """
        if (curr_time - self.start_time) < self.signal_delay:
            return 0

        # Flip state and reschedule when toggle time is reached
        if curr_time >= self.next_jitter_toggle:
            # Flip TTL state
            self.curr_signal = 1 - self.curr_signal

            # Calculate next toggle time with jitter
            half_period = 0.5 / max(self.signal_freq, 1e-6)
            p = min(0.999, max(1e-6, base_unit * max(self.signal_freq, 1e-6)))
            extra = np.random.geometric(p) * base_unit  # jitter duration (s)
            extra = min(extra, max_extra)  # cap long tails
            self.next_jitter_toggle = curr_time + half_period + extra

        return self.curr_signal

    def get_sin_wave(self, curr_time: float) -> float:
        """Generate low-amplitude sine wave (0 to 0.5 range).

        Args:
            curr_time: Current wall-clock time

        Returns:
            Value between 0 and 0.5
        """
        if (curr_time - self.start_time) < self.signal_delay:
            curr_signal = 0
        else:
            curr_signal = np.round((np.sin((curr_time * self.signal_freq)) + 1) / 4, 4)
        return curr_signal

    def flip_every_frame(self, curr_time: float) -> float:
        """Toggle signal between 0 and 1 every frame.

        Args:
            curr_time: Current wall-clock time

        Returns:
            0 or 1 (opposite of previous value)
        """
        if (curr_time - self.start_time) < self.signal_delay:
            curr_signal = 0
        else:
            curr_signal = 1 - self.curr_signal
        return curr_signal
