import array
import machine
import micropython
import random
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

# Gamma correction makes fades, twinkles and trails dim evenly to the eye
# (LED output is linear, eyes aren't). 1.0 turns it off. Colors an effect
# designs should go through true_color() so they look the same either way.
GAMMA = 2.2

# Temporal dithering: alternate between neighbouring LED levels frame to
# frame to show the shades in between. Only levels of at least
# DITHER_FLOOR are dithered (below that, slow 0/1 alternation reads as
# flicker), and the in-between amount is rounded to 1/DITHER_STEPS so
# the alternation stays quick enough to blend.
DITHER = True
DITHER_FLOOR = 2
DITHER_STEPS = 8

_table = None


def set_brightness(value):
    """Set the global brightness (0.0-1.0) applied by show_all().

    The slider is perceptual when gamma is on: 0.5 looks half as bright.
    """
    global BRIGHTNESS, _table
    BRIGHTNESS = max(0.0, min(1.0, value))
    _table = None


def set_gamma(value):
    """Change gamma live (1.0 = off), e.g. to compare from the REPL.
    Restart the scene afterwards so its true_color() colors are redone."""
    global GAMMA, _table
    GAMMA = max(1.0, value)
    _table = None


def true_color(color):
    """The color to draw so the LEDs show `color` exactly as they would
    with gamma off. Use it for designed colors (palettes, backgrounds) so
    gamma only changes how things fade and blend, never their hue."""
    m = max(color)
    if GAMMA == 1.0 or m == 0:
        return (int(color[0]), int(color[1]), int(color[2]))
    k = 255 * (m / 255) ** (1 / GAMMA) / m
    return (int(color[0] * k + 0.5), int(color[1] * k + 0.5), int(color[2] * k + 0.5))


def all_pixels(strips, color):
    """Set every pixel on every strand."""
    for strip in strips:
        strip.fill(color)


def _build_table():
    """Per-pixel scale, indexed by the pixel's brightest channel m:
    256 * out(m) / m, where out() applies brightness then gamma.

    Scaling all three channels by the same factor keeps the hue; only how
    bright the pixel is gets gamma-corrected. Values are 8.8 fixed point,
    and never exceed 256, so channel * scale fits in 16 bits.
    """
    t = array.array("H", [0] * 256)
    for m in range(1, 256):
        out = 255 * (BRIGHTNESS * m / 255) ** GAMMA
        t[m] = min(256, int(256 * out / m + 0.5))
    return t


@micropython.viper
def _render(src: ptr8, dst: ptr8, err: ptr8, n: int, table: ptr16,
            dither: int, floor: int, step_shift: int):
    """Gamma/brightness via table, then temporal dithering, into dst.

    err holds each channel's leftover fraction (out of 256) from earlier
    frames; adding it before rounding down spreads the fraction over time.
    """
    half = (1 << step_shift) >> 1
    i = 0
    while i < n:
        a = src[i]
        b = src[i + 1]
        c = src[i + 2]
        m = a
        if b > m:
            m = b
        if c > m:
            m = c
        t = table[m]
        j = i
        while j < i + 3:
            x = src[j] * t
            hi = x >> 8
            if dither != 0 and hi >= floor:
                lo = (((x & 255) + half) >> step_shift) << step_shift
                acc = err[j] + lo
                hi += acc >> 8
                err[j] = acc & 255
            else:
                hi = (x + 128) >> 8
            if hi > 255:
                hi = 255
            dst[j] = hi
            j += 1
        i += 3


_out_bufs = {}
_err_bufs = {}


def show_all(strips):
    """Push updates to all strips with brightness, gamma and dithering.

    These are applied only to what's written to the hardware: each strip's
    bytes are rendered into a scratch buffer, which is swapped in for the
    write and then swapped back out. Effects (e.g. the ripple code in
    stars.py) read back the buffer to compute the next frame, so baking
    any of this into it would compound every frame.

    The rendering runs as viper code on the raw bytes. Going through
    strip[i] instead (neopixel is plain Python on the Pico) took ~77ms a
    frame, capping every scene at ~12 FPS whenever the lights were dimmed.
    """
    global _table
    if BRIGHTNESS >= 1.0 and GAMMA == 1.0:
        for strip in strips:
            strip.write()
        return

    if _table is None:
        _table = _build_table()
    # Fractions are rounded to multiples of 256 / DITHER_STEPS.
    step_shift = 0
    s = 256 // DITHER_STEPS
    while s > 1:
        s >>= 1
        step_shift += 1
    for strip in strips:
        buf = strip.buf
        key = id(strip)
        out = _out_bufs.get(key)
        if out is None or len(out) != len(buf):
            out = _out_bufs[key] = bytearray(len(buf))
            # Random starting leftovers so neighbouring pixels don't all
            # step up on the same frame.
            _err_bufs[key] = bytearray(random.getrandbits(8) for _ in range(len(buf)))
        _render(buf, out, _err_bufs[key], len(buf), _table,
                1 if DITHER else 0, DITHER_FLOOR, step_shift)
        strip.buf = out
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
