import serial
import matplotlib.pyplot as plt
from datetime import datetime
import time
import numpy as np

# Configure the serial port
ser = serial.Serial(
    "/dev/tty.usbmodem146854901", 9600
)  # Adjust 'COM1' to your serial port and 9600 to your baud rate
print("connected")
# Prepare to collect data
data = []
timestamps = []
start_time = time.time()

# Record data for 10 seconds
timeout = time.time() + 10  # 10 seconds from now

while True:
    # Read data from serial port
    if time.time() > timeout:
        break  # Timeout reached, stop reading

    if ser.in_waiting > 0:
        line = ser.readline().decode("utf-8").rstrip()
        now = time.time() - start_time  # Current time
        print(f"[{now}] Received: {line}")

        # Record data and timestamp
        timestamps.append(now)
        data.append(float(line))  # Assuming incoming data is a float

# Close the serial port
ser.close()

# Plot the data
data = np.array(data)

plt.plot(timestamps, data)
# times = np.array(timestamps)[data > 0]
# print(np.mean(np.diff(times)))
plt.title("Serial Data")
plt.xlabel("Time")
plt.ylabel("Value")
plt.grid(True)
plt.xticks(rotation=45)
plt.show()

df = {"timestamps": timestamps, "data": data}

np.save(arr=df, file="photodidode", allow_pickle=True)

"""
plt.plot(np.diff(np.array(times).astype('float')))
plt.title('Serial Data')
plt.xlabel('Time')
plt.ylabel('Value')
plt.grid(True)
plt.xticks(rotation=45)
plt.show()
"""
