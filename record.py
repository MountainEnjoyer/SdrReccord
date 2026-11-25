import numpy as np
import matplotlib.pyplot as plt
from matplotlib import mlab
from rtlsdr import RtlSdr

def avg_spectrum(x, fs, nfft=1024):
    rows = len(x) // nfft
    blocks = x[:rows * nfft].reshape(rows, nfft) * np.hanning(nfft)
    power = np.mean(np.abs(np.fft.fft(blocks, axis=1)) ** 2, axis=0)
    freqs = np.fft.fftshift(np.fft.fftfreq(nfft, d=1 / fs))
    return freqs, np.fft.fftshift(10 * np.log10(power + 1e-12))

NFFT = 1024
station = 101.1e6
fs = 2.4e6
duration = 5

sdr = RtlSdr()
sdr.sample_rate = fs
sdr.center_freq = station + 250e3
sdr.gain = 10

try:
    block = 2**21                               # 2,097,152 samples = 4 MB per read
    n_blocks = int(duration * fs) // block + 1

    chunks = []
    for _ in range(n_blocks):
        chunks.append(sdr.read_samples(block))
    samples = np.concatenate(chunks)[:int(duration * fs)]
    fname = f"fm_{station/1e6:.1f}MHz.npy"
    peak = max(np.abs(samples.real).max(), np.abs(samples.imag).max())
    clipped = np.mean((np.abs(samples.real) > 0.99) | (np.abs(samples.imag) > 0.99))
    print(f"peak {peak:.3f}, clipped {clipped * 100:.3f} % of samples")
    np.save(fname, samples.astype(np.complex64))

finally:
    sdr.close()   # always release the dongle, even on Ctrl+C or error

samples = np.load(fname)

fig, (ax1) = plt.subplots(1, 1, figsize=(9, 6))

freqs, power_db = avg_spectrum(samples, fs)

ax1.plot(freqs / 1e3, power_db)
ax1.set_xlabel("Frequency (kHz)", loc="right")
ax1.set_ylabel("Power (dB)")
ax1.set_title("Frequencies")
ax1.grid(True)

plt.show()
