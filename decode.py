import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from scipy.io import wavfile

fname = "fm_101.1MHz.npy"
fs = 2.4e6          # recording rate
fA = -250e3         # where the station sits in the recording
num_taps = 201      # first filter
dec1 = 10           # 2.4 MS/s -> 240 kS/s
dec2 = 5            # 240 kS/s -> 48 kS/s
fs1 = fs / dec1
fs2 = fs1 / dec2

def avg_spectrum(x, fs, nfft=1024):
    rows = len(x) // nfft
    blocks = x[:rows * nfft].reshape(rows, nfft) * np.hanning(nfft)
    power = np.mean(np.abs(np.fft.fft(blocks, axis=1)) ** 2, axis=0)
    freqs = np.fft.fftshift(np.fft.fftfreq(nfft, d=1 / fs))
    return freqs, np.fft.fftshift(10 * np.log10(power + 1e-12))

x = np.load(fname).astype(np.complex128)
t = np.arange(len(x)) / fs
y = x * np.exp(-2j * np.pi * fA * t)
taps = signal.firwin(num_taps, 100e3, fs=fs)
z = signal.lfilter(taps, 1.0, y)[num_taps:][::dec1]

audio = np.angle(z[1:] * np.conj(z[:-1]))

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8))

F, P = avg_spectrum(z, fs1)
ax1.plot(F / 1e3, P)
ax1.set_title("Station after shift, filter and ÷10")
ax1.set_xlabel("Frequency (kHz)", loc="right")
ax1.grid(True)

F, P = avg_spectrum(audio, fs1)
ax2.plot(F / 1e3, P)
ax2.set_xlim(0, 60)
ax2.set_title("After FM demodulation")
ax2.set_xlabel("Frequency (kHz)", loc="right")
ax2.grid(True)

plt.tight_layout()
plt.show()


a = np.exp(-1 / (50e-6 * fs1))
audio = signal.lfilter([1 - a], [1, -a], audio)

taps2 = signal.firwin(101, 15e3, fs=fs1)
audio = signal.lfilter(taps2, 1.0, audio)[101:][::dec2]

audio = audio / np.max(np.abs(audio)) * 0.9
wavfile.write("fm_101.1MHz.wav", int(fs2), (audio * 32767).astype(np.int16))
