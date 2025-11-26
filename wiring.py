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

def all_pixels(strips, color):
    """Set every pixel on every strand."""
    for strip in strips:
        strip.fill(color)


def show_all(strips):
    """Push updates to all strips."""
    for strip in strips:
        strip.show()


def clear(strips):
    all_pixels(strips, (0,0,0))
    show_all(strips)
