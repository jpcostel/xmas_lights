from machine import Pin, SPI
import neopixel
import time

ROWS = 8
COLS = 25
PIXELS = ROWS * COLS

# ---- NeoPixels ----
np = neopixel.NeoPixel(Pin(18), PIXELS)

def grid_to_pixel(row, col):
    if row % 2 == 0:
        return row * COLS + (COLS - 1 - col)
    else:
        return row * COLS + col

# ---- SPI (slave) ----
spi = SPI(
    0,
    baudrate=1_000_000,
    polarity=0,
    phase=0,
    bits=8,
    firstbit=SPI.MSB,
    sck=Pin(18),
    mosi=Pin(19),
    miso=Pin(16)  # unused but required
)

cs = Pin(17, Pin.IN, Pin.PULL_UP)

FRAME_LEN = 26  # 25 heights + checksum
rx = bytearray(FRAME_LEN)
heights = [0] * COLS

def read_frame():
    if cs.value() == 0:
        spi.readinto(rx)
        checksum = sum(rx[:25]) & 0xFF
        if checksum == rx[25]:
            for i in range(COLS):
                heights[i] = min(ROWS, rx[i])

def render():
    np.fill((0, 0, 0))
    for col in range(COLS):
        for row in range(heights[col]):
            idx = grid_to_pixel(row, col)
            np[idx] = (20 + row * 30, 255 - row * 20, 50)
    np.write()

while True:
    read_frame()
    render()
    time.sleep_ms(16)
