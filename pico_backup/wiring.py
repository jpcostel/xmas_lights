import board
import neopixel

# -------------------------
# HARDWARE CONFIG
# -------------------------

PIXELS_PER_STRAND = 100
NUM_STRANDS = 2

PINS = [board.D18, board.D19]

# Initialize strips
strips = [
    neopixel.NeoPixel(pin, PIXELS_PER_STRAND)
    for pin in PINS
]

def get_color_mask(strips):
    """
    Generates a list of colors (the rainbow pattern) for every pixel.
    This acts as our "Source of Truth" so colors never get corrupted or faded.
    """
    # Your color palette
    ci = ((255,255,0), (0,0,255), (255,0,0), (0,255,0), (0,255,255), (255,0,255))
    
    mask = []
    for s_idx, strip in enumerate(strips):
        strand_mask = []
        # Use range(len(strip)) to be safe, or your constant PIXELS_PER_STRAND
        for i in range(len(strip)):
            index = i % len(ci)
            strand_mask.append(ci[index])
            # print("Index:{}\ni:{}\npixel:{}".format(index, i, ci[index]))
        mask.append(strand_mask)
    return mask


def all_pixels(strips, color):
    """Set every pixel on every strand."""
    for strip in strips:
        strip.fill(color)


def show_all(strips):
    """Push updates to all strips."""
    for strip in strips:
        strip.write()


def clear(strips):
    all_pixels(strips, (0,0,0))
    show_all(strips)
