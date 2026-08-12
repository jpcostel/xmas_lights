import machine
import neopixel

# -------------------------
# HARDWARE CONFIG
# -------------------------

PIXELS_PER_STRAND = 100
NUM_STRANDS = 2

PINS = [0,1]

GOLD_PALETTE = [
    (255,  32,   0),   
    (255,  48,   0),   
    (255,  64,   0),   
    (255, 128,   0),   
    (255, 196,  32),   
]

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
    
    color_indices = [XMAS_PALLET, EMBER_PALETTE, WATER_PALETTE, GOLD_PALETTE]
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


BRIGHTNESS = 1.0

def set_brightness(value):
    """Set the global brightness scale (0.0-1.0) applied by show_all()."""
    global BRIGHTNESS
    BRIGHTNESS = max(0.0, min(1.0, value))


def all_pixels(strips, color):
    """Set every pixel on every strand."""
    for strip in strips:
        strip.fill(color)


def show_all(strips):
    """Push updates to all strips, scaled by the global brightness.

    Scaling is applied only to what's written to the hardware, then the
    strip's buffer is restored to its unscaled values. Effects (e.g. the
    ripple code in stars.py) read back strip[i] to compute the next frame,
    so leaving BRIGHTNESS baked into the buffer would compound the dimming
    every frame instead of applying it once per frame.
    """
    if BRIGHTNESS >= 1.0:
        for strip in strips:
            strip.write()
        return

    for strip in strips:
        original = [strip[i] for i in range(len(strip))]
        for i, (r, g, b) in enumerate(original):
            strip[i] = (int(r * BRIGHTNESS), int(g * BRIGHTNESS), int(b * BRIGHTNESS))
        strip.write()
        for i, color in enumerate(original):
            strip[i] = color


def clear(strips):
    all_pixels(strips, (0,0,0))
    show_all(strips)
