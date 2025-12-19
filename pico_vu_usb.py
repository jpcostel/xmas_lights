import sys
import time
import select
from machine import Pin
import neopixel

# [0]   0xAA        start byte
# [1]   mode        (future use, ignore for now)
# [2..26] heights  25 bytes (0–8)
# [27]  checksum   sum(bytes[1..26]) & 0xFF

ROWS = 8
COLS = 25
PIXELS_PER_STRAND = ROWS * COLS

# ---- Neopixel setup (adjust pins/count to your wiring) ----
np = neopixel.NeoPixel(Pin(18), PIXELS_PER_STRAND)

# ---- Grid mapping (same logic you already use) ----
def grid_to_pixel(row, col):
    if row < 4:
        strand = 0
        local_row = row
    else:
        strand = 1
        local_row = row - 4

    if local_row % 2 == 0:
        index = local_row * COLS + (COLS - 1 - col)
    else:
        index = local_row * COLS + col

    return index  # single strip assumed; adapt if dual

# ---- USB frame state ----
FRAME_LEN = 28
frame_buf = bytearray()
latest_heights = [0] * COLS

poll = select.poll()
poll.register(sys.stdin, select.POLLIN)

def read_usb_frames():
    global frame_buf, latest_heights

    if poll.poll(0):
        data = sys.stdin.read()
        if data:
            frame_buf.extend(data)

    while len(frame_buf) >= FRAME_LEN:
        if frame_buf[0] != 0xAA:
            frame_buf.pop(0)
            continue

        frame = frame_buf[:FRAME_LEN]
        frame_buf = frame_buf[FRAME_LEN:]

        checksum = sum(frame[1:27]) & 0xFF
        if checksum != frame[27]:
            continue

        latest_heights = list(frame[2:27])

# ---- Rendering ----
def render_columns(heights):
    np.fill((0, 0, 0))

    for col in range(COLS):
        h = heights[col]
        for row in range(h):
            idx = grid_to_pixel(row, col)
            # simple color gradient
            color = (
                int(32 + row * 28),
                int(255 - row * 20),
                50
            )
            np[idx] = color

    np.write()

# ---- Main loop ----
FRAME_TIME_MS = 16  # ~60 FPS

while True:
    read_usb_frames()
    render_columns(latest_heights)
    time.sleep_ms(FRAME_TIME_MS)
