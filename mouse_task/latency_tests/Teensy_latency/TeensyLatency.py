import threading
import time
import serial


class TeensyLatency:
    def __init__(self, com, baudrate):
        self.com = com
        self.baudrate = baudrate
        self.input_data = []
        self.input_data_time = []
        self.reading_teensy = True
        self.stop_event = threading.Event()
        self._init_additional_fields()
        self.start_read_buffer()

    def _init_additional_fields(self):
        return None

    def _handle_line(self, line: str, now: float):
        self.input_data.append(float(line))
        self.input_data_time.append(now)

    def read_on_thread(self):
        while self.reading_teensy and not self.stop_event.is_set():
            line = self.ser.readline().decode("utf-8").rstrip()
            now = time.time()  # Current time
            try:
                self._handle_line(line, now)
            except Exception:
                continue

    def start_read_buffer(self):
        """Start the reader thread for serial buffer, writer for `input_data`, save start time."""
        self.ser = serial.Serial(self.com, self.baudrate)
        self.start_read_time = time.time()
        self._reader_thread = threading.Thread(target=self.read_on_thread, daemon=True)
        self._reader_thread.start()
    def _stop_reading(self):
        """Stop reading from teensy and close serial connection."""
        self.reading_teensy = False
        self.stop_event.set()
    def close_serial(self):
        self._stop_reading()
        if hasattr(self, '_reader_thread') and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2.0)
        self.ser.close()