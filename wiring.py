import board
import neopixel

# -------------------------
# HARDWARE CONFIG
# -------------------------

PIXELS_PER_STRAND = 100
NUM_STRANDS = 2

DATA_PINS = [
    board.D18,   # Strand 0
    board.D19,   # Strand 1
]

# Initialize strips
strips = [
    neopixel.NeoPixel(
        DATA_PINS[i],
        PIXELS_PER_STRAND,
        auto_write=False,
        pixel_order=neopixel.GRB
    )
    for i in range(NUM_STRANDS)
]
