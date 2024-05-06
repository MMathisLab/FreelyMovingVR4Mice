import matplotlib.pyplot as plt
import matplotlib.animation as animation
import time
import serial

fig = plt.figure()
ax1 = fig.add_subplot(1, 1, 1)

# Replace the port with the one your arduino is connected to your computer
ser = serial.Serial("/dev/cu.usbmodem11302", 9600)

x_data = []
y_data = []
start_time = time.time()


def animate(ser):
    # Read data from serial port
    data = float(ser.readline().decode("utf-8").rstrip())
    x_data.append(time.time() - start_time)
    y_data.append(data)
    ax1.clear()
    ax1.plot(x_data[-100:], y_data[-100:])


ani = animation.FuncAnimation(fig, animate(ser), interval=1000 / 40, save_count=40)
plt.show()
