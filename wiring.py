import board
import neopixel

# -------------------------
# HARDWARE CONFIG
# -------------------------

PIXELS_PER_STRAND = 50
NUM_STRANDS = 4

DATA_PINS = [
    board.D18,   # Strand 0
    board.D19,   # Strand 1
    board.D20,   # Strand 2
    board.D21    # Strand 3
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

def colorize(strips):
    """Loop through and modulo to change the color of each pixel
    take the existing RGB value as reference brightness"""
    for strip in strips:
        for i in range(strip.n)

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
