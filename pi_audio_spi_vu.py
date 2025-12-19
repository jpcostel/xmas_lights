import numpy as np
import sounddevice as sd
import spidev
import time

# ---- SPI ----
spi = spidev.SpiDev()
spi.open(0, 0)          # SPI0 CS0
spi.max_speed_hz = 1_000_000
spi.mode = 0

# ---- Audio ----
SAMPLE_RATE = 48000
BLOCK = 1024
COLS = 25
ROWS = 8

# ---- FFT bands ----
freqs = np.fft.rfftfreq(BLOCK, 1 / SAMPLE_RATE)
edges = np.logspace(np.log10(50), np.log10(16000), COLS + 1)

bands = [
    np.where((freqs >= edges[i]) & (freqs < edges[i + 1]))[0]
    for i in range(COLS)
]

window = np.hanning(BLOCK)

def send_frame(heights):
    frame = list(heights)
    checksum = sum(frame) & 0xFF
    frame.append(checksum)
    spi.xfer2(frame)

def audio_cb(indata, frames, time_info, status):
    samples = indata[:, 0] * window
    fft = np.abs(np.fft.rfft(samples))

    heights = []
    for idx in bands:
        power = np.mean(fft[idx]) if len(idx) else 0
        level = int(min(ROWS, np.log10(power + 1e-6) * 3))
        heights.append(max(0, level))

    send_frame(heights)

with sd.InputStream(
    channels=1,
    samplerate=SAMPLE_RATE,
    blocksize=BLOCK,
    callback=audio_cb
):
    print("SPI audio visualizer running")
    while True:
        time.sleep(1)
