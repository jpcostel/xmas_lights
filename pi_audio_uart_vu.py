import numpy as np
import sounddevice as sd
import serial
import time

# ---- UART ----
ser = serial.Serial(
    "/dev/serial0",
    baudrate=1_000_000,
    timeout=0
)

# ---- Audio ----
DEVICE = 1
SAMPLE_RATE = 48000   # Shure MV7 native
BLOCK = 1024
ROWS = 8
COLS = 25

# ---- FFT bands (log-spaced) ----
freqs = np.fft.rfftfreq(BLOCK, 1 / SAMPLE_RATE)
edges = np.logspace(np.log10(50), np.log10(16000), COLS + 1)
bands = [
    np.where((freqs >= edges[i]) & (freqs < edges[i + 1]))[0]
    for i in range(COLS)
]

window = np.hanning(BLOCK)

def send_frame(heights):
    frame = bytearray(29)
    frame[0] = 0xAA
    frame[1] = 0x01
    for i, h in enumerate(heights):
        frame[2 + i] = h
    frame[27] = sum(frame[1:27]) & 0xFF
    ser.write(frame)

def audio_cb(indata, frames, time_info, status):
    samples = indata[:, 0] * window
    fft = np.abs(np.fft.rfft(samples))

    heights = []
    for idx in bands:
        power = np.mean(fft[idx]) if len(idx) else 0
        level = int(np.clip(np.log10(power + 1e-6) * 3.0, 0, ROWS))
        heights.append(level)
    print(heights)
    send_frame(heights)

def play():
    with sd.InputStream(
        device=DEVICE,
        channels=1,
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK,
        callback=audio_cb
    ):
        print("UART audio visualizer running")
        while True:
            time.sleep(1)


play()