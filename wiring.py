import machine
import micropython
import neopixel
from grid import grid_to_pixel, ROWS, COLS

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


@micropython.viper
def _scale_bytes(src: ptr8, dst: ptr8, n: int, k: int):
    """dst[i] = src[i] * k / 256, compiled to machine code."""
    for i in range(n):
        dst[i] = (src[i] * k) >> 8


_dim_bufs = {}


def show_all(strips):
    """Push updates to all strips, scaled by the global brightness.

    Scaling is applied only to what's written to the hardware: each strip's
    unscaled bytes are scaled into a scratch buffer, which is swapped in for
    the write and then swapped back out. Effects (e.g. the ripple code in
    stars.py) read back the buffer to compute the next frame, so baking
    BRIGHTNESS into it would compound the dimming every frame.

    The scaling runs as viper code on the raw bytes. Going through
    strip[i] instead (neopixel is plain Python on the Pico) took ~77ms a
    frame, capping every scene at ~12 FPS whenever the lights were dimmed.
    """
    if BRIGHTNESS >= 1.0:
        for strip in strips:
            strip.write()
        return

    k = int(BRIGHTNESS * 256)
    for strip in strips:
        buf = strip.buf
        dim = _dim_bufs.get(id(strip))
        if dim is None or len(dim) != len(buf):
            dim = _dim_bufs[id(strip)] = bytearray(len(buf))
        _scale_bytes(buf, dim, len(buf), k)
        strip.buf = dim
        try:
            strip.write()
        finally:
            # Ctrl-C (how scenes are stopped) can land mid-write.
            strip.buf = buf


def strand_map(strips):
    """Raw byte offsets for every pixel, indexed like the strips themselves.

    Returns m[strand][index] = (buf, r, g, b): the strand's byte buffer and
    the offsets of that pixel's red, green and blue bytes, so effects can
    write buf[r] = red etc. directly. Going through strip[i] = (r, g, b)
    costs ~70us a pixel on the Pico (neopixel's __setitem__ is Python),
    which adds up when a scene redraws all 200 pixels every frame.
    """
    m = []
    for strip in strips:
        order = strip.ORDER
        bpp = strip.bpp
        buf = strip.buf
        m.append([
            (buf, i * bpp + order[0], i * bpp + order[1], i * bpp + order[2])
            for i in range(len(strip))
        ])
    return m


def pixel_map(strips):
    """Like strand_map, but indexed by grid position: px[row][col]."""
    m = strand_map(strips)
    px = []
    for row in range(ROWS):
        line = []
        for col in range(COLS):
            strand, index = grid_to_pixel(row, col)
            line.append(m[strand][index])
        px.append(line)
    return px


def snapshot(strips):
    """Copy of every strip's current bytes, for restore() each frame."""
    return [bytes(strip.buf) for strip in strips]


def restore(strips, snap):
    """Put back bytes saved by snapshot(): a fast way to redraw a static
    background before drawing the moving parts on top."""
    for strip, saved in zip(strips, snap):
        strip.buf[:] = saved


def clear(strips):
    all_pixels(strips, (0,0,0))
    show_all(strips)
