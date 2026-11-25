# SdrReccord

Records a real FM radio station with an RTL-SDR dongle, then decodes it to an audio file: the first working receiver of a multi-mode software-defined radio (SDR) project.

`record.py` captures 5 seconds of raw I/Q samples around a broadcast station. `decode.py` turns them into sound: it shifts the station to 0 Hz, filters it, lowers the sample rate, demodulates the FM, applies de-emphasis and writes a 48 kHz WAV file. Everything between the antenna and the speakers is done in Python with NumPy and SciPy.

It is the second phase of the project, built on the three DSP exercises before it:

1. [FreqFinder](https://github.com/MountainEnjoyer/FreqFinder): find a frequency with the FFT.
2. [FrequencyShiftFilter](https://github.com/MountainEnjoyer/FrequencyShiftFilter): shift a signal to 0 Hz and filter it.
3. [FrequencyShiftFilterDecimation](https://github.com/MountainEnjoyer/FrequencyShiftFilterDecimation): lower the sample rate without aliasing.

## Repository contents

```
SdrReccord/
├── record.py          # records 5 s of I/Q samples from the dongle and plots their spectrum
├── decode.py          # decodes a recording to a WAV file and plots each stage
├── exec.sh            # runs record.py, decode.py, then plays the result with mpv
├── fm_101.1MHz.npy    # a sample recording: 101.1 MHz, 2.4 MS/s, 5 s (96 MB)
├── fm_101.1MHz.wav    # the audio decoded from it: 48 kHz, 16-bit, mono, 5 s
└── README.md
```

The sample recording means `decode.py` can be run without any radio hardware.

## Requirements

- Linux (developed and tested on Arch Linux)
- An RTL-SDR dongle (RTL2832U with an R820T/R820T2 tuner) and its antenna, for recording
- Python 3.8 or later, with NumPy, SciPy, Matplotlib and pyrtlsdr in a virtual environment
- The `rtl-sdr` driver, Tk for the plot windows, and `mpv` to play the result

## Installation (Arch Linux)

### 1. System packages

```bash
sudo pacman -S --needed python tk git rtl-sdr mpv
```

- `rtl-sdr` is the driver (`librtlsdr`) that pyrtlsdr talks to.
- `tk` lets Matplotlib open its plot windows. Without it the scripts run, but print `FigureCanvasAgg is non-interactive` and show nothing.
- `mpv` plays the decoded WAV at the end of `exec.sh`.

### 2. Clone the repository

```bash
git clone https://github.com/MountainEnjoyer/SdrReccord.git
cd SdrReccord
```

### 3. Virtual environment and Python packages

Arch marks its system Python as externally managed ([PEP 668](https://peps.python.org/pep-0668/)), so the packages go into a local `.venv`:

```bash
python -m venv .venv
.venv/bin/pip install numpy scipy matplotlib "pyrtlsdr[lib]"
```

Use `pip`, not `pipx`: these are libraries the scripts import, not command-line programs.

`pyrtlsdr[lib]` also installs a bundled copy of the driver. It matters because recent pyrtlsdr versions call a driver function (`rtlsdr_set_dithering`) that Arch's `rtl-sdr` package does not provide; see Troubleshooting if the import still fails.

## Usage

### Record, decode and listen

From the repository folder:

```bash
./exec.sh
```

It runs three steps in order:

1. `record.py` records 5 seconds from the station and opens a plot of their spectrum. **Close the window to continue.**
2. `decode.py` decodes the recording and opens a plot of two stages. **Close the window to continue.**
3. `mpv` plays `fm_101.1MHz.wav`.

Each run records again and replaces `fm_101.1MHz.npy` and `fm_101.1MHz.wav`.

### Decode the included recording only (no dongle needed)

```bash
.venv/bin/python decode.py
mpv fm_101.1MHz.wav
```

## How it works

### Recording (`record.py`)

| Step | Code | Why |
| --- | --- | --- |
| Tune 250 kHz above the station | `center_freq = station + 250e3` | The dongle produces a false peak at its exact center frequency (the DC spike). Tuning beside the station keeps it clean; the station then sits at −250 kHz in the recording. |
| Sample at 2.4 MS/s | `sample_rate = 2.4e6` | A 2.4 MHz wide view, at the fastest rate most computers sustain over USB without losing samples. |
| Read in blocks of 2²¹ samples | `read_samples(2**21)` in a loop | Linux limits a single USB transfer to 16 MB by default; one 5-second read would exceed it (`LIBUSB_ERROR_NO_MEM`). |
| Check for clipping | `peak`, `clipped` | I and Q are each scaled to −1…+1; samples at the limit mean the gain is too high. |
| Save as `complex64` | `np.save(...)` | 8 bytes per sample instead of 16: 96 MB for 5 seconds. |

The spectrum is averaged over 1024-sample blocks (Welch's method) by `avg_spectrum()`. A single FFT of millions of samples gives 1 Hz bins whose values jump by ±20 dB, which hides the stations; averaging makes them readable.

### Decoding (`decode.py`)

| Stage | Code | Sample rate after |
| --- | --- | --- |
| **Shift** the station from −250 kHz to 0 Hz | `y = x * np.exp(-2j * np.pi * fA * t)` | 2.4 MS/s |
| **Filter** to ±100 kHz, the width of an FM station (201-tap FIR) | `signal.firwin(201, 100e3, fs=fs)` | 2.4 MS/s |
| **Decimate** by 10 | `[num_taps:][::10]` | 240 kS/s |
| **Demodulate FM** | `np.angle(z[1:] * np.conj(z[:-1]))` | 240 kS/s, now real |
| **De-emphasis**, 50 µs (Europe) | `signal.lfilter([1 - a], [1, -a], audio)` | 240 kS/s |
| **Audio filter** to 15 kHz, then decimate by 5 | `signal.firwin(101, 15e3, fs=fs1)`, `[::5]` | 48 kS/s |
| **Normalize** to 90 % of full scale and write a 16-bit WAV | `wavfile.write(...)` | 48 kS/s |

**Why 201 taps:** after decimating by 10, the visible range is ±120 kHz, so everything beyond it must already be removed or it folds back onto the station (aliasing). At 2.4 MS/s, 201 taps reach −40 dB before 120 kHz; 101 taps would only get there at 136 kHz.

**FM demodulation:** a broadcast station encodes its audio in how fast its signal rotates in the I/Q plane. Multiplying each sample by the conjugate of the previous one gives a complex number whose angle is the rotation between them; that angle, sample after sample, is the audio. With the ±75 kHz deviation of broadcast FM at 240 kS/s, it stays within about ±2 radians.

**De-emphasis:** stations boost treble before transmitting; this one-pole low-pass filter turns it back down, and the high-frequency hiss with it.

**Audio filter:** keeps the 0–15 kHz program and removes the 19 kHz stereo pilot and everything above it, which would otherwise be heard as a whine or fold into the 48 kHz audio.

## Results with the included recording

Measured on `fm_101.1MHz.npy` (101.1 MHz, gain 10):

| Check | Result |
| --- | --- |
| Station above the noise floor | 19 dB, well above the roughly 10 dB FM needs |
| Peak sample level | 0.608, no clipping |
| Spectrum after FM demodulation | 19 kHz stereo pilot about 25 dB above its surroundings; stereo energy around 38 kHz; the double-lobed RDS signal around 57 kHz |
| Output | `fm_101.1MHz.wav`: 48 kHz, 16-bit, mono, 5 s |

The 19 kHz pilot is the quickest proof that everything before the audio stage works: it is only there if the shift, filter, decimation and demodulation are all correct.

Expected imperfections: some background hiss (the station is only 19 dB above the noise with the stock antenna), and possibly a few faint ticks where recording blocks join, since a few samples can be lost between two USB reads.

## Configuration

`record.py`:

| Setting | Default | Description |
| --- | --- | --- |
| `station` | `101.1e6` | Station frequency in Hz. Pick a strong local station. |
| `fs` | `2.4e6` | Sample rate. |
| `duration` | `5` | Recording length in seconds. Each second takes 19 MB on disk and about 38 MB of RAM. |
| `sdr.gain` | `10` | Receiver gain in dB. Raise it if the station is buried; lower it if samples clip. |

`decode.py`:

| Setting | Default | Description |
| --- | --- | --- |
| `fname` | `"fm_101.1MHz.npy"` | Recording to decode. |
| `fA` | `-250e3` | Where the station sits in the recording. Always −250 kHz with `record.py`. |
| `num_taps` | `201` | Length of the channel filter. |
| `dec1`, `dec2` | `10`, `5` | Decimation factors: 2.4 MS/s → 240 kS/s → 48 kS/s. |

When recording another station, change `station` in `record.py` and the two file names in `decode.py` and `exec.sh`.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'rtlsdr'` | pyrtlsdr is not installed in this project's `.venv` | `.venv/bin/pip install "pyrtlsdr[lib]"` (the package is named `pyrtlsdr`, the module `rtlsdr`). |
| `pipx install` refuses with "No apps associated with package" | pipx is for command-line programs | Use the virtual environment's pip, as in Installation, step 3. |
| `AttributeError: ... librtlsdr.so: undefined symbol` (`rtlsdr_set_dithering`) | Recent pyrtlsdr expects a driver feature Arch's `rtl-sdr` lacks | Install `"pyrtlsdr[lib]"`; if the error remains, `.venv/bin/pip install "pyrtlsdr==0.2.93" setuptools`. |
| `LIBUSB_ERROR_NO_MEM`, "Could not read … bytes" | A single read larger than the 16 MB USB transfer limit | Read in blocks, as `record.py` does. |
| `FigureCanvasAgg is non-interactive`, no window opens | Matplotlib found no window system | `sudo pacman -S tk`; check that `MPLBACKEND` is not set to `Agg`. |
| `exec.sh` seems stuck after the first plot | `plt.show()` waits until its window is closed | Close the plot window. |
| No station visible in the spectrum | Weak reception, or no station at that frequency | Extend the antenna rods to about 75 cm each, move it near a window, raise the gain, or pick another station. |
| Distorted, crackling audio | Clipping during recording | Lower `sdr.gain` until `clipped` reads 0.000 %. |
| Only noise in the WAV, no 19 kHz peak after demodulation | The station is not at `fA` in the recording | Check the recording's spectrum: the station must be at −250 kHz. |

## Roadmap

- **Phase 1, DSP fundamentals:** FreqFinder, FrequencyShiftFilter, FrequencyShiftFilterDecimation.
- **Phase 2, offline FM (this repository):** record a station and decode it to a WAV file.
- **Phase 3, more analog modes:** AM (air band), narrowband FM, SSB.
- **Phase 4, real-time:** continuous reading and live audio.
- **Later:** a modular multi-mode architecture, a spectrum and waterfall interface, and digital modes (RDS, ADS-B, APRS).

## Further reading

- [PySDR: A Guide to SDR and DSP using Python](https://pysdr.org), chapters on FM, filters and the RTL-SDR
- [pyrtlsdr](https://github.com/pyrtlsdr/pyrtlsdr)
- [SciPy signal processing documentation](https://docs.scipy.org/doc/scipy/reference/signal.html)
