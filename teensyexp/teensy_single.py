import time
import threading
import struct
import numpy as np
import serial
import statistics
from collections import deque

class Teensy(object):
    """
    Teensy/Arduino serial interface with:
      - framed binary reader (end sentinel)  OR CSV reader
      - optional clock sync ('X' -> 'SYNC <t_dev_us>')
      - host-aligned timestamps
      - thread-safe deques for input/output buffers (unbounded)
    """

    def __init__(self, serial_port, baudrate, inputs, outputs,
                 read_mode='framed',   # 'framed' or 'csv'
                 timeout=0.05,         # >0 so readline() works for CSV
                 csv_expected=5        # number of CSV fields from device
                 ):
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.timeout = float(timeout)
        self.read_mode = read_mode
        self.csv_expected = int(csv_expected)

        # framing (binary mode)
        self.end_bytes = struct.pack('hh', -32767, 32767)

        # runtime
        self.inputs = list(inputs) if inputs else []
        self.n_inputs = len(self.inputs)
        self.outputs = outputs or {}

        # unbounded thread-safe deques
        self.input_data = deque()
        self.output_data = deque()

        self.reading = False
        self.offset = None
        self.offset_quality = None

        self.connect_serial()
        if self.read_mode == 'csv' and not self.inputs:
            # Default CSV names (Arduino: micros,analog,digital,L_on,R_on)
            self.inputs = ['t_dev_us', 'analog', 'digital', 'L_on', 'R_on']
            self.n_inputs = len(self.inputs)

        if self.n_inputs > 0 or self.read_mode == 'csv':
            self.start_read_buffer()

    # -------------------- Serial --------------------

    def connect_serial(self):
        """Open port and clear buffers."""
        while True:
            try:
                self.ser = serial.Serial(self.serial_port, self.baudrate, timeout=self.timeout)
                break
            except serial.SerialException:
                pass
        time.sleep(2.0)  # give device time after reset
        self.ser.reset_input_buffer()

    # -------------------- Reader thread --------------------

    def start_read_buffer(self):
        """Start background reader thread."""
        self.start_read_time = time.time()
        self.reading = True
        threading.Thread(target=self.read_on_thread, daemon=True).start()

    def read_on_thread(self):
        if self.read_mode == 'csv':
            self._read_loop_csv()
        else:
            self._read_loop_framed()

    def _read_loop_csv(self):
        while self.reading:
            line = self.ser.readline()
            if not line:
                continue
            t_recv = time.time()
            try:
                s = line.decode('utf-8', errors='replace').strip()
            except Exception:
                continue
            if not s or s.startswith('SYNC '):
                continue

            parts = s.split(',')
            if len(parts) != self.csv_expected:
                continue

            try:
                t_dev_us = float(parts[0])
                parsed = [t_dev_us] + [int(p) if p.strip().lstrip('-').isdigit() else float(p)
                                       for p in parts[1:]]
            except Exception:
                continue

            t_host_est = (self.offset + t_dev_us/1e6) if self.offset is not None else None
            record = {'t_recv': t_recv, 't_host_est': t_host_est}
            for k, v in zip(self.inputs, parsed):
                record[k] = v
            self.input_data.append(record)

    def _read_loop_framed(self):
        buffer = b''
        item_size = 2 * self.n_inputs
        while self.reading:
            data = self.ser.read(64)
            if not data:
                continue
            buffer += data
            if self.end_bytes in buffer:
                chunks = buffer.split(self.end_bytes)
                for frame in chunks[:-1]:
                    if len(frame) < item_size:
                        continue
                    try:
                        vals = struct.unpack('h' * self.n_inputs, frame[-item_size:])
                    except struct.error:
                        continue
                    t_recv = time.time()
                    record = {'t_recv': t_recv}
                    for k, v in zip(self.inputs, vals):
                        record[k] = v
                    self.input_data.append(record)
                buffer = chunks[-1]

    # -------------------- Public read API --------------------

    def read(self, index=-1, key=None):
        if len(self.input_data) == 0 or abs(index) > len(self.input_data):
            return {} if key is None else -1
        # deque supports indexing but is O(n); fine for tail reads
        rec = self.input_data[index]
        if key is None:
            return dict(rec)
        return rec.get(key, -1)

    # -------------------- Writing / commands --------------------

    def write(self, output, params=[]):
        """
        Send a command defined in self.outputs:
          outputs = {
            'start': {'command':'A'},
            'stop' : {'command':'Z'},
            'left' : {'command':'L','params':['dur_ms']},
            'right': {'command':'R','params':['dur_ms']},
            'tone' : {'command':'T','params':['freq_hz','dur_ms']},
            'sync' : {'command':'X'}
          }
        """
        if type(params) is not list:
            params = [params]

        if output not in self.outputs:
            raise KeyError(f"Unknown output '{output}'")

        spec = self.outputs[output]
        if 'params' in spec and len(params) != len(spec['params']):
            print(f"WARNING :: command={output} not sent; expected {len(spec['params'])} params, got {len(params)}")
            return

        self.output_data.append([time.time(), output] + params)
        command = spec['command'].encode('ascii')
        for p in params:
            command += struct.pack('<h', int(p))
        self.ser.write(command)
        self.ser.flush()

    # -------------------- Clock sync --------------------

    def sync_once(self):
        """
        One-shot clock sync.
        PC sends 'X'; device replies 'SYNC <t_dev_us>\\n'.
        Returns (offset, rtt) where:
            offset maps device->host: t_host_est = offset + t_dev_us/1e6
        """
        t0 = time.time()
        self.ser.write(b'X')
        line = self.ser.readline().decode('ascii', errors='replace').strip()
        t3 = time.time()

        if not line.startswith('SYNC '):
            raise RuntimeError(f'Bad sync reply: {line!r}')
        try:
            t_dev_us = float(line.split()[1])
        except Exception:
            raise RuntimeError(f'Bad sync payload: {line!r}')

        rtt = t3 - t0
        offset = t3 - (t_dev_us/1e6 + rtt/2.0)
        return offset, rtt

    def calibrate_offset(self, attempts=15, keep_best=5, sleep_s=0.02):
        """Take several sync samples; keep lowest-RTT subset; set self.offset."""
        samples = []
        for _ in range(int(attempts)):
            try:
                off, rtt = self.sync_once()
                samples.append((rtt, off))
            except Exception:
                pass
            time.sleep(sleep_s)
        if not samples:
            raise RuntimeError("SYNC failed (no samples)")
        samples.sort(key=lambda x: x[0])
        best = samples[:max(1, int(keep_best))]
        offsets = [off for (rtt, off) in best]
        self.offset = statistics.median(offsets)
        self.offset_quality = best[0][0]
        return self.offset, self.offset_quality

    # -------------------- Utilities --------------------

    def stop(self):
        self.reading = False

    def get_input_data(self, format='array'):
        """Return input_data as numpy array (best-effort for CSV/framed)."""
        if not self.input_data:
            return np.array([])
        keys = ['t_recv', 't_host_est'] + self.inputs
        rows = []
        # convert deque -> list snapshot to avoid growth during iteration
        snapshot = list(self.input_data)
        for rec in snapshot:
            row = [rec.get(k, np.nan) for k in keys]
            rows.append(row)
        return np.array(rows)

    def get_output_data(self):
        return list(self.output_data)

    def reset(self):
        self.input_data.clear()
        self.output_data.clear()

    def close(self):
        self.stop()
        try:
            self.ser.close()
        except Exception:
            pass
