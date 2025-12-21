from machine import UART, Pin
import neopixel
import time

from wiring import *

# ---- NeoPixels ----
# np = neopixel.NeoPixel(Pin(18), PIXELS)

# def grid_to_pixel(row, col):
#     # serpentine wiring
#     if row % 2 == 0:
#         return row * COLS + (COLS - 1 - col)
#     else:
#         return row * COLS + col

from grid import grid_to_pixel

# ---- UART1 ----
uart = UART(
    1,                  # UART1 (not UART0)
    baudrate=1_000_000,
    tx=Pin(8),          # optional / unused
    rx=Pin(9)           # Pi TX connects here
)

FRAME_LEN = 29
buf = bytearray()
heights = [0] * COLS

def read_uart():
    global buf, heights

    while uart.any():
        data = uart.read()
        print(data)
        if data:
            buf.extend(data)

    while len(buf) >= FRAME_LEN:
        if buf[0] != 0xAA:
            buf.pop(0)
            continue

        frame = buf[:FRAME_LEN]
        buf = buf[FRAME_LEN:]

        checksum = sum(frame[1:27]) & 0xFF
        if checksum != frame[27]:
            continue

        heights[:] = frame[2:27]

def render():
    for strip in strips:
        strip.fill((0,0,0))
    for col in range(COLS):
        h = min(ROWS, heights[col])
        for row in range(h):
            strand, idx = grid_to_pixel(row, col)
            strips[strand][idx] = (
                20 + row * 30,
                255 - row * 20,
                60
            )
    for strip in strips:
        strip.write()

# ---- Main loop ----
FRAME_MS = 16

while True:
    print("read uart")
    read_uart()
    print("render")
    render()
    time.sleep_ms(FRAME_MS)
