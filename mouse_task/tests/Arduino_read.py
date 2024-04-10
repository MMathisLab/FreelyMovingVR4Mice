import serial
import matplotlib.pyplot as plt
from datetime import datetime
import time
import numpy as np

# Configure the serial port
ser = serial.Serial('/dev/tty.usbmodem1402', 9600)  # Adjust 'COM1' to your serial port and 9600 to your baud rate

# Prepare to collect data
data = []
timestamps = []

# Record data for 10 seconds
timeout = time.time() + 10  # 10 seconds from now

while True:
    # Read data from serial port
    if time.time() > timeout:
        break  # Timeout reached, stop reading

    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8').rstrip()
        now = datetime.now().strftime('%H:%M:%S.%f')[:-3]  # Current time
        print(f'[{now}] Received: {line}')
        
        # Record data and timestamp
        timestamps.append(datetime.now())
        data.append(float(line))  # Assuming incoming data is a float

# Close the serial port
ser.close()

# Plot the data
data = np.array(data) > 340
data = abs(np.diff(data, prepend=0))
plt.plot(timestamps, data, marker='o')
times = np.array(timestamps)[data > 0]
print(np.mean(np.diff(times)))
plt.title('Serial Data')
plt.xlabel('Time')
plt.ylabel('Value')
plt.grid(True)
plt.xticks(rotation=45)
plt.show()

plt.plot(np.array(np.diff(times)).astype('float'))
plt.title('Serial Data')
plt.xlabel('Time')
plt.ylabel('Value')
plt.grid(True)
plt.xticks(rotation=45)
plt.show()