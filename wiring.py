#!/home/jpcostel/Projects/xmas_lights/.venv/bin/python3
import board
import neopixel

# Configuration
NUM_STRANDS = 4          # total data pins (you have 2 now)
PIXELS_PER_STRAND = 50   # 25 rings up + 25 down
RINGS_PER_STRAND = PIXELS_PER_STRAND // 2

# Data GPIOs (update as needed)
DATA_PINS = [
    board.D18,  # strand 0
    board.D19,  # strand 1
    board.D20,  # strand 2 (future)
    board.D21,  # strand 3 (future)
]

# Initialize only active strands (you have 2 right now)
active_strands = 2
pixels = [
    neopixel.NeoPixel(pin, PIXELS_PER_STRAND, auto_write=False, pixel_order=neopixel.GRB)
    for pin in DATA_PINS[:active_strands]
]

def set_ring(ring_index, color):
    """
    Set the same color on all pixels in a given horizontal ring across all strands.
    ring_index: 0..RINGS_PER_STRAND-1
    color: (r, g, b)
    """
    if ring_index < 0 or ring_index >= RINGS_PER_STRAND:
        raise ValueError("Invalid ring index")

    for strand_id, strip in enumerate(pixels):
        # Determine pixel indices for this ring in the up/down loop
        up_pixel = ring_index
        down_pixel = PIXELS_PER_STRAND - 1 - ring_index

        strip[up_pixel] = color
        strip[down_pixel] = color

def show():
    """Write data to all strands."""
    for strip in pixels:
        strip.show()

def clear():
    """Turn all LEDs off."""
    for strip in pixels:
        strip.fill((0, 0, 0))
        strip.show()
