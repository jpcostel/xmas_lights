import machine
import neopixel

# -------------------------
# HARDWARE CONFIG
# -------------------------

PIXELS_PER_STRAND = 100
NUM_STRANDS = 2

PINS = [0,1]

EMBER_PALETTE = [
    (120,  60,   0),   
    (180, 120,   0),   
    (220, 180,   0),   
    (255, 220, 120),   
    (160, 200,  20),   
]

WATER_PALETTE = [
    (  0,  60, 120),    # Deep Blue – depth
    (  0, 120, 180),    # Ocean Blue – mid-water
    (  0, 180, 220),    # Aqua Flow – motion highlights
    (120, 220, 255),    # Surface Light – reflections
    ( 20, 200, 160),    # Teal Current – organic movement
]

XMAS_PALLET = [
    (255,255,0),        # Yellow
    (0,0,255),          # Blue
    (255,0,0),          # Red
    (0,255,0),          # Green
    (0,255,255),        # Teal
    (255,0,255)         # Purple
]

# Initialize strips
strips = [
    neopixel.NeoPixel(machine.Pin(pin), PIXELS_PER_STRAND)
    for pin in PINS
]

def get_color_mask(strips, pallet=0):
    """
    Generates a list of colors (the rainbow pattern) for every pixel.
    This acts as our "Source of Truth" so colors never get corrupted or faded.
    An optional pallet index can be supplied to change the color pallet as follows:
    0 - xmas-lights
    1 - warm embers
    2 - cool water
    """
    # Your color palette
    
    color_indices = [XMAS_PALLET, EMBER_PALETTE, WATER_PALETTE]
    ci = color_indices[pallet]

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
