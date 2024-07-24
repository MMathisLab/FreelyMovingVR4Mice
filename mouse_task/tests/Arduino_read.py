import serial
import matplotlib.pyplot as plt
import time
import numpy as np


def arduino_read(t=10):
    # Configure the serial port
    ser = serial.Serial(
        "/dev/cu.usbmodem146851301",
        9600,
        # "/dev/cu.usbmodem146854901",
        # 9600,
    )  # Adjust 'COM1' to your serial port and 9600 to your baud rate
    print("connected")
    # Prepare to collect data
    data = []
    timestamps = []
    start_time = time.time()

    # Record data for 10 seconds
    timeout = start_time + t

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
    return data, timestamps


if __name__ == "__main__":
    data, timestamps = arduino_read(t=10)

    # Plot the data
    data = np.array(data)

    import scipy

    N = 2
    Wn = 0.1

    b, a = scipy.signal.butter(N, Wn, "low")
    output_signal = scipy.signal.filtfilt(b, a, data)

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
