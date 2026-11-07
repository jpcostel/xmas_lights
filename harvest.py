import array
import micropython
import utime
from canvas import Canvas, PERM, drift, gradient, noise, q8
from grid import ROWS, COLS

# ============================================================
# CONFIGURATION
# ============================================================
# Slow waves of autumn color, like light through leaves: two layers of
# soft blobs drift across each other in different directions to pick
# each LED's color, and a third, slower one shades them lighter and
# darker. Nothing moves quickly.

# Colors from one end of the range to the other (as they'd look with
# gamma off). Most of the wall sits around the middle.
HARVEST_COLORS = [
    (0.0, (60, 0, 45)),        # deep plum
    (0.35, (170, 20, 5)),      # rust
    (0.6, (255, 75, 0)),       # amber
    (0.82, (255, 140, 0)),     # gold
    (1.0, (255, 185, 40)),     # pale gold
]
CONTRAST = 1.7                 # spread colors toward the ends of the range

WAVE_WIDTH = 7.0               # columns across one wave...
WAVE_HEIGHT = 5.0              # ...and rows
WAVE_SPEED = (0.5, 0.35)       # columns/sec of the first layer...
WAVE_SPEED_2 = (-0.4, -0.2)    # ...and the second, crossing it
SHADE_WIDTH = 9.0              # columns across a light or dark patch
SHADE_SPEED = (0.25, -0.15)
SHADE_DEPTH = 0.4              # darkest patches, as a fraction of full

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# DRAWING
# ============================================================

@micropython.viper
def _glow(light: ptr16, perm, p: ptr32, palette: ptr16):
    """Fill light[] with the color waves; p holds the layers' scales
    and positions."""
    cols = p[0]
    rows = p[1]
    sx = p[2]
    sy = p[3]
    x1 = p[4]
    y1 = p[5]
    x2 = p[6]
    y2 = p[7]
    shade_s = p[8]
    xs = p[9]
    ys = p[10]
    contrast = p[11]
    depth = p[12]
    o = 0
    row = 0
    while row < rows:
        col = 0
        while col < cols:
            n1 = int(noise(col * sx + x1, row * sy + y1, perm))
            n2 = int(noise(col * sx + x2 + 20000, row * sy + y2 + 9000, perm))
            v = 128 + ((((n1 + n2) >> 1) - 128) * contrast >> 8)
            if v < 0:
                v = 0
            elif v > 255:
                v = 255
            n3 = int(noise(col * shade_s + xs + 40000, row * shade_s + ys, perm))
            k = depth + (((256 - depth) * n3) >> 8)
            v *= 3
            light[o] = (int(palette[v]) * k) >> 8
            light[o + 1] = (int(palette[v + 1]) * k) >> 8
            light[o + 2] = (int(palette[v + 2]) * k) >> 8
            o += 3
            col += 1
        row += 1


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def harvest_glow(strips):
    canvas = Canvas(strips)
    light = canvas.light
    palette = gradient(HARVEST_COLORS)
    p = array.array("i", [COLS, ROWS, q8(1 / WAVE_WIDTH), q8(1 / WAVE_HEIGHT), 0, 0, 0, 0,
                          q8(1 / SHADE_WIDTH), 0, 0, q8(CONTRAST), q8(SHADE_DEPTH)])
    # Where each layer is in the noise it's drawn from.
    at = [0.0] * 6
    speeds = (WAVE_SPEED[0] / WAVE_WIDTH, WAVE_SPEED[1] / WAVE_HEIGHT,
              WAVE_SPEED_2[0] / WAVE_WIDTH, WAVE_SPEED_2[1] / WAVE_HEIGHT,
              SHADE_SPEED[0] / SHADE_WIDTH, SHADE_SPEED[1] / SHADE_WIDTH)
    last = utime.ticks_ms()

    while True:
        frame_start = utime.ticks_ms()
        dt = min(100, utime.ticks_diff(frame_start, last)) / 1000
        last = frame_start
        for i in range(6):
            # Moving the noise one way moves the waves the other.
            at[i] = drift(at[i], -speeds[i], dt)
            p[4 + i] = q8(at[i])

        _glow(light, PERM, p, palette)
        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
