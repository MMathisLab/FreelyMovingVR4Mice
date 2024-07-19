import numpy as np
from scipy.signal import butter, filtfilt, freqz
import matplotlib.pyplot as plt
from Arduino_read import arduino_read


def butter_lowpass(cutoff, fs, order=5):
    return butter(order, cutoff, fs=fs, btype="low", analog=False)


def butter_lowpass_filter(data, cutoff, fs, order=5):
    b, a = butter_lowpass(cutoff, fs, order=order)
    y = filtfilt(b, a, data)
    return y


data, t = arduino_read(t=15)
data = np.array(data)
print(data.size)


# Filter requirements.
order = 6
fs = 8496.0  # sample rate, Hz
cutoff = 40  # desired cutoff frequency of the filter, Hz

# Get the filter coefficients so we can check its frequency response.
Wn = 2 * cutoff / fs
b, a = butter(order, Wn, btype="low")

# Plot the frequency response.
w, h = freqz(b, a, fs=fs, worN=8000)
plt.subplot(2, 1, 1)
plt.plot(w, np.abs(h), "b")
plt.plot(cutoff, 0.5 * np.sqrt(2), "ko")
plt.axvline(cutoff, color="k")
plt.xlim(0, 200)
plt.title("Lowpass Filter Frequency Response")
plt.xlabel("Frequency [Hz]")
plt.grid()

# Filter the data, and plot both the original and filtered signals.
filtered_signal = filtfilt(b, a, data)

plt.subplot(2, 1, 2)
plt.plot(t, data, "b-", label="data")
plt.plot(t, filtered_signal, "r-", linewidth=2, label="filtered data")
plt.xlabel("Time [sec]")
plt.grid()
plt.legend()

plt.subplots_adjust(hspace=0.35)
plt.show()
