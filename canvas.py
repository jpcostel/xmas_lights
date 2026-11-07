"""A real-light drawing surface for scenes made of smooth shapes and fields.

Scenes draw into Canvas.light: each LED's r, g, b as real light output (as
they'd be with gamma off), at LIGHT steps per LED level so soft edges and
dim glows fade finer than the strip's 0-255. Mixing in real light keeps a
shape's brightness steady as it moves between LEDs. show() gamma-encodes
it into the strips and calls show_all.

The per-LED work is meant to run as viper integer code: on the Pico every
float operation allocates memory, which holds a scene that does float math
per LED to ~10 fps. Positions, angles and fractions are fixed point, x256
("Q8").
"""
import array
import micropython
import wiring
from wiring import show_all, pixel_map
from grid import ROWS, COLS

LIGHT = 16

# VIPER_PTR16_BUG: on the Pico (MicroPython 1.27), when a small viper
# function indexes a ptr16 with a plain local variable, e.g. light[i],
# the generated code doubles that variable in place (it turns the index
# into a byte offset in the variable's own register). Later uses of it
# then point twice as far along: a clear loop skipped most entries, and
# an add wrote past the end of light[] and froze the Pico. Index with an
# expression instead (light[i + 0]) when the variable is used again.


def q8(v):
    """A float as Q8 fixed point, rounded."""
    return int(v * 256 + (0.5 if v >= 0 else -0.5))


def to_light(color):
    """A color (0-255 per channel, as it'd look with gamma off) in light units."""
    return [c * LIGHT for c in color]


def gradient(stops, size=256):
    """Colors at size even steps along stops [(position 0..1, color)],
    blended in real light, as an array('H') of r, g, b light units: the
    entry for step i starts at 3 * i."""
    out = array.array("H", [0] * (size * 3))
    for i in range(size):
        f = i / (size - 1)
        k = 0
        while k < len(stops) - 2 and f > stops[k + 1][0]:
            k += 1
        (p0, c0), (p1, c1) = stops[k], stops[k + 1]
        w = 0.0 if p1 == p0 else min(1.0, max(0.0, (f - p0) / (p1 - p0)))
        for ch in range(3):
            out[3 * i + ch] = int((c0[ch] + (c1[ch] - c0[ch]) * w) * LIGHT + 0.5)
    return out


# Lattice values for noise(): a fixed shuffle of 0-255 (a simple LCG, so
# it's the same on the Pico and in tests).
def _shuffle():
    p = list(range(256))
    s = 12345
    for i in range(255, 0, -1):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        j = (s >> 8) % (i + 1)
        p[i], p[j] = p[j], p[i]
    return bytearray(p)


PERM = _shuffle()

# noise() repeats every NOISE_PERIOD units in x and y. Scenes that scroll
# through it should keep their position wrapped to this (see drift()):
# the Pico's floats are single precision, so a position that just keeps
# growing gets coarse after hours and overflows Q8 after weeks.
NOISE_PERIOD = 256


def drift(position, speed, dt):
    """position moved on by speed * dt, wrapped to NOISE_PERIOD."""
    return (position + speed * dt) % NOISE_PERIOD


@micropython.viper
def noise(x: int, y: int, perm: ptr8) -> int:
    """Smooth value noise, 0-255, at Q8 point (x, y): blobs about one unit
    across that blend smoothly from one to the next. Pass PERM as perm."""
    ix = (x >> 8) & 255
    iy = (y >> 8) & 255
    fx = x & 255
    fy = y & 255
    sx = (fx * fx * (768 - 2 * fx)) >> 16     # smoothstep
    sy = (fy * fy * (768 - 2 * fy)) >> 16
    px0 = int(perm[ix])
    px1 = int(perm[(ix + 1) & 255])
    a = int(perm[(px0 + iy) & 255])
    b = int(perm[(px1 + iy) & 255])
    c = int(perm[(px0 + iy + 1) & 255])
    d = int(perm[(px1 + iy + 1) & 255])
    lo = a + (((b - a) * sx) >> 8)
    hi = c + (((d - c) * sx) >> 8)
    return lo + (((hi - lo) * sy) >> 8)


@micropython.viper
def _encode(light: ptr16, buf: ptr8, where: ptr16, n: int, table: ptr16):
    """Gamma-encode light[] into one strip's bytes, keeping each LED's hue.
    where holds (light index, r, g, b byte offsets) per LED; table[m] is
    the scale (x4096) for an LED whose brightest channel is m."""
    i = 0
    while i < n * 4:
        o = where[i]
        r = int(light[o])
        g = int(light[o + 1])
        b = int(light[o + 2])
        m = r
        if g > m:
            m = g
        if b > m:
            m = b
        t = int(table[m])
        v = (r * t + 2048) >> 12
        buf[where[i + 1]] = v if v < 255 else 255
        v = (g * t + 2048) >> 12
        buf[where[i + 2]] = v if v < 255 else 255
        v = (b * t + 2048) >> 12
        buf[where[i + 3]] = v if v < 255 else 255
        i += 4


@micropython.viper
def _add(light: ptr16, o: int, r: int, g: int, b: int):
    # Indexed by o + 0, never plain o: see VIPER_PTR16_BUG.
    top = 255 * 16
    v = int(light[o + 0]) + r
    light[o + 0] = v if v < top else top
    v = int(light[o + 1]) + g
    light[o + 1] = v if v < top else top
    v = int(light[o + 2]) + b
    light[o + 2] = v if v < top else top


class Canvas:
    def __init__(self, strips):
        self.strips = strips
        pixels = pixel_map(strips)
        top = 255 * LIGHT
        inv_gamma = 1 / wiring.GAMMA
        # table[m]: scale for an LED whose brightest channel is m (in
        # light units) so show_all's gamma gives back m's light. Under
        # half an LED level stays off: the faintest edges otherwise show
        # as stray specks.
        self.table = array.array("H", [0] * (top + 1))
        for m in range(LIGHT // 2, top + 1):
            self.table[m] = min(65535, int(4096 * 255 * (m / top) ** inv_gamma / m + 0.5))

        # Where each LED's light goes in its strip's bytes.
        self.wheres = []
        for strip in strips:
            w = []
            for row in range(ROWS):
                for col in range(COLS):
                    buf, ro, go, bo = pixels[row][col]
                    if buf is strip.buf:
                        w += (3 * (row * COLS + col), ro, go, bo)
            self.wheres.append((strip.buf, array.array("H", w), len(w) // 4))

        self.light = array.array("H", [0] * (ROWS * COLS * 3))
        # Cleared by copying this in, not a viper loop: see VIPER_PTR16_BUG.
        self._dark = array.array("H", self.light)

    def clear(self):
        self.light[:] = self._dark

    def glow(self, x, y, color, amount=1.0):
        """Add a point of light at (x, y), anywhere between LEDs: it's
        shared between the four LEDs around it by how close each is, so
        it gives off the same light wherever it is and glides smoothly.
        color is in light units."""
        ix = int(x // 1)
        iy = int(y // 1)
        fx = x - ix
        fy = y - iy
        for row, wy in ((iy, 1 - fy), (iy + 1, fy)):
            if 0 <= row < ROWS:
                for col, wx in ((ix, 1 - fx), (ix + 1, fx)):
                    if 0 <= col < COLS:
                        w = wx * wy * amount
                        if w > 0.0:
                            _add(self.light, 3 * (row * COLS + col),
                                 int(color[0] * w), int(color[1] * w), int(color[2] * w))

    def show(self):
        for buf, where, n in self.wheres:
            _encode(self.light, buf, where, n, self.table)
        show_all(self.strips)
