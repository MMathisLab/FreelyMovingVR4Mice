import numpy as np

from latency_tests.Teensy_latency.TeensyLatency import TeensyLatency


class TeensyLatencySync(TeensyLatency):
    def _init_additional_fields(self):
        self.input_data_teensy_time = list()
        self.input_data_ttl = list()

    def _handle_line(self, line, now):
        line = line.strip()
        if not line:
            return

        input_parts = [part.strip() for part in line.split(",")]
        self.input_data.append(input_parts[0])
        self.input_data_time.append(now)
        self.input_data_ttl.append(input_parts[1] if len(input_parts) > 1 else None)
        self.input_data_teensy_time.append(
            input_parts[2] if len(input_parts) > 2 else None
        )