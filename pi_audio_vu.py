import numpy as np
import sounddevice as sd
import serial
import time

# ---- USB serial ----
SERIAL_PORT = "/dev/ttyACM0"  # adjust if needed
BAUD = 115200
ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0)

# ---- Audio ----
SAMPLE_RATE = 48000
BLOCK_SIZE = 1024
CHANNELS = 1
DTYPE = 'float32'

# ---- Visualization ----
COLS = 25
ROWS = 8
FREQ_MIN = 50
FREQ_MAX = 16000

MIC_DEVICE = None
for i, d in enumerate(sd.query_devices()):
    if "MV7" in d['name']:
        MIC_DEVICE = i
if MIC_DEVICE is None:
    raise RuntimeError("MV7 not found")

# ---- FFT bin setup (log-spaced) ----
fft_bins = np.fft.rfftfreq(BLOCK_SIZE, 1 / SAMPLE_RATE)
band_edges = np.logspace(
    np.log10(FREQ_MIN),
    np.log10(FREQ_MAX),
    COLS + 1
)

band_indices = [
    np.where((fft_bins >= band_edges[i]) &
             (fft_bins < band_edges[i + 1]))[0]
    for i in range(COLS)
]

window = np.hanning(BLOCK_SIZE)

# ---- Frame builder ----
def send_frame(heights):
    frame = bytearray(28)
    frame[0] = 0xAA
    frame[1] = 0x01  # mode

    for i, h in enumerate(heights):
        frame[2 + i] = int(h)

    frame[27] = sum(frame[1:27]) & 0xFF
    ser.write(frame)

# ---- Audio callback ----
def audio_callback(indata, frames, time_info, status):
    samples = indata[:, 0]
    fft = np.abs(np.fft.rfft(samples * window))

    heights = []
    for idxs in band_indices:
        if len(idxs) == 0:
            power = 0
        else:
            power = np.mean(fft[idxs])

        # log compression + scaling
        level = np.log10(power + 1e-6) * 2.5
        level = max(0, min(ROWS, int(level)))
        heights.append(level)

    print(heights)
    send_frame(heights)
    

# ---- Start stream ----
print("Running audio visualizer...")
with sd.InputStream(
    device=MIC_DEVICE,
    channels=CHANNELS,
    samplerate=SAMPLE_RATE,
    blocksize=BLOCK_SIZE,
    dtype=DTYPE,
    callback=audio_callback
):
    time.sleep(1)
