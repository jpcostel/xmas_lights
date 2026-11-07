import array
import math
import micropython
import random
import utime
from canvas import Canvas, PERM, drift, gradient, noise, q8, to_light
from grid import ROWS, COLS

# ============================================================
# CONFIGURATION
# ============================================================
# A row of candles along the bottom of the mantle, each flame
# flickering softly on its own with a warm halo around it. Now and then
# one gutters, dipping and wavering before it steadies, and once in a
# while a gentle draft passes along the row, leaning each flame in turn.

CANDLES = [                    # (column, rows of wax)
    (2, 3),
    (7, 2),
    (12, 4),
    (17, 2),
    (22, 3),
]

# Flame color from its edge to its hottest (as they'd look with gamma off).
FLAME_COLORS = [
    (0.0, (0, 0, 0)),
    (0.3, (90, 14, 0)),        # deep orange, the tip
    (0.6, (255, 80, 2)),       # orange
    (0.85, (255, 150, 25)),    # yellow
    (1.0, (255, 210, 110)),    # warm white, the heart of it
]
WAX_COLOR = (255, 175, 95)
WAX_GLOW = (0.01, 0.06)        # wax brightness at its foot and at its top
HALO_COLOR = (255, 110, 25)
HALO_GLOW = 0.07               # halo brightness around the flame...
HALO_RADIUS = 3.5              # ...fading out over this many columns
HALO_TALL = 1.3                # stretched upward by this much

FLAME_LENGTH = 2.0             # rows
WICK_GAP = 0.15                # rows between the wax and the flame
FLAME_HEAT = 1.2               # heat at the flame's heart (1 = just warm white)
BREATH = 0.1                   # slow swell and fade of each flame...
BREATH_HZ = 0.35
FLICKER = 0.06                 # ...and its quicker, smaller flicker
FLICKER_HZ = 4.0
SWAY = 0.12                    # columns a flame wanders side to side
SWAY_HZ = 0.5

GUTTER_EVERY_S = (25, 70)      # each candle gutters this often...
GUTTER_S = (1.8, 3.2)          # ...for this long
GUTTER_DIM = 0.5               # down to this bright, with the flame...
GUTTER_SHRINK = 0.45           # ...this much shorter...
GUTTER_FLICKER = 0.35          # ...wavering this much...
GUTTER_HZ = 7.0
GUTTER_SWAY = 0.35             # ...and swaying this many columns

DRAFT_EVERY_S = (45, 120)      # a draft passes along the row this often...
DRAFT_LEAN = 0.4               # ...leaning the flames this many columns...
DRAFT_SPEED = 8.0              # ...moving this many columns/sec
DRAFT_WIDTH = 6.0              # ...across this many columns
DRAFT_DIM = 0.85

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# DRAWING
# ============================================================

@micropython.viper
def _halo(light: ptr16, c: ptr32, p: ptr32):
    """Add a soft glow around a point. c: x, y, brightness (Q8); p:
    cols, rows, 65536 / radius^2 across and up, color in light units,
    and how many LEDs out to look."""
    cols = p[0]
    rows = p[1]
    ix = p[2]
    iy = p[3]
    cr = p[4]
    cg = p[5]
    cb = p[6]
    reach = p[7]
    x = c[0]
    y = c[1]
    k = c[2]
    top = 255 * 16
    row = (y >> 8) - reach
    if row < 0:
        row = 0
    last_row = (y >> 8) + reach + 1
    if last_row > rows:
        last_row = rows
    while row < last_row:
        dy = (row << 8) - y
        dy2 = (((dy * dy) >> 8) * iy) >> 16
        col = (x >> 8) - reach
        if col < 0:
            col = 0
        last_col = (x >> 8) + reach + 1
        if last_col > cols:
            last_col = cols
        while col < last_col:
            dx = (col << 8) - x
            f = 256 - ((((dx * dx) >> 8) * ix) >> 16) - dy2
            if f > 0:
                a = (((f * f) >> 8) * k) >> 8
                o = 3 * (row * cols + col)
                v = int(light[o + 0]) + ((cr * a) >> 8)
                light[o + 0] = v if v < top else top
                v = int(light[o + 1]) + ((cg * a) >> 8)
                light[o + 1] = v if v < top else top
                v = int(light[o + 2]) + ((cb * a) >> 8)
                light[o + 2] = v if v < top else top
            col += 1
        row += 1


@micropython.viper
def _flame(light: ptr16, c: ptr32, p: ptr32, palette: ptr16):
    """Add a flame: a column of heat, hottest just above its base and
    cooling to its tip, shared between the two columns its x lies
    between. c: x, base y, length, heat (Q8); p: cols, rows."""
    cols = p[0]
    rows = p[1]
    x = c[0]
    base = c[1]
    length = c[2]
    hot = c[3]
    top = 255 * 16
    col = x >> 8
    right = x & 255
    row = (base >> 8)
    if row < 0:
        row = 0
    while row < rows:
        # 0 at the base, 256 at the tip. (Divided as positive numbers:
        # dividing negative ones may round differently on the Pico.)
        d = (row << 8) - base
        if d < 0:
            u = 0 - (((0 - d) << 8) // length)
        else:
            u = (d << 8) // length
        if u >= 256:
            break
        # Fades in just below the base, then cools toward the tip.
        a = 0
        if u > -50:
            a = ((u + 50) << 8) // 90
        if a > 256:
            a = 256
        heat = (((a * (256 - u)) >> 8) * hot) >> 8
        if heat > 255:
            heat = 255
        if heat > 0:
            heat *= 3
            r = int(palette[heat + 0])
            g = int(palette[heat + 1])
            b = int(palette[heat + 2])
            o = 3 * (row * cols + col)
            if col >= 0 and col < cols:
                w = 256 - right
                v = int(light[o + 0]) + ((r * w) >> 8)
                light[o + 0] = v if v < top else top
                v = int(light[o + 1]) + ((g * w) >> 8)
                light[o + 1] = v if v < top else top
                v = int(light[o + 2]) + ((b * w) >> 8)
                light[o + 2] = v if v < top else top
            if col + 1 >= 0 and col + 1 < cols:
                v = int(light[o + 3]) + ((r * right) >> 8)
                light[o + 3] = v if v < top else top
                v = int(light[o + 4]) + ((g * right) >> 8)
                light[o + 4] = v if v < top else top
                v = int(light[o + 5]) + ((b * right) >> 8)
                light[o + 5] = v if v < top else top
        row += 1


# ============================================================
# CANDLES
# ============================================================

class Candle:
    def __init__(self, i, col, wax):
        self.col = col
        self.wax = wax
        # Each candle reads its own stretch of noise.
        self.seed = 9000 * (i + 1)
        self.breath_at = random.uniform(0, 200)
        self.flicker_at = random.uniform(0, 200)
        self.sway_at = random.uniform(0, 200)
        self.gutter_in = random.uniform(*GUTTER_EVERY_S)
        self.gutter_s = 0.0
        self.gutter_age = 0.0

    def step(self, dt):
        """Returns (sway, brightness, length) for this frame, before any draft."""
        self.breath_at = drift(self.breath_at, BREATH_HZ, dt)
        self.flicker_at = drift(self.flicker_at, FLICKER_HZ, dt)
        self.sway_at = drift(self.sway_at, SWAY_HZ, dt)
        breath = (noise(q8(self.breath_at), self.seed, PERM) - 128) / 128
        flicker = (noise(q8(self.flicker_at), self.seed + 3000, PERM) - 128) / 128
        sway = (noise(q8(self.sway_at), self.seed + 6000, PERM) - 128) / 128

        # Guttering: eases in and out over its whole length.
        g = 0.0
        if self.gutter_s:
            self.gutter_age += dt
            if self.gutter_age >= self.gutter_s:
                self.gutter_s = 0.0
                self.gutter_in = random.uniform(*GUTTER_EVERY_S)
            else:
                g = math.sin(math.pi * self.gutter_age / self.gutter_s)
                g *= g
        else:
            self.gutter_in -= dt
            if self.gutter_in <= 0:
                self.gutter_s = random.uniform(*GUTTER_S)
                self.gutter_age = 0.0

        bright = 1 + BREATH * breath + (FLICKER + GUTTER_FLICKER * g) * flicker
        bright *= 1 - (1 - GUTTER_DIM) * g
        length = FLAME_LENGTH * (1 + 0.5 * BREATH * breath + FLICKER * flicker) * (1 - GUTTER_SHRINK * g)
        return (SWAY + GUTTER_SWAY * g) * sway, bright, length


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def candlelight(strips):
    canvas = Canvas(strips)
    light = canvas.light
    palette = gradient(FLAME_COLORS)
    wax_color = to_light(WAX_COLOR)
    candles = [Candle(i, col, wax) for i, (col, wax) in enumerate(CANDLES)]

    c = array.array("i", [0] * 4)
    reach = int(HALO_RADIUS * HALO_TALL) + 1
    halo = array.array("i", [COLS, ROWS, int(65536 / HALO_RADIUS ** 2),
                             int(65536 / (HALO_RADIUS * HALO_TALL) ** 2)]
                       + to_light(HALO_COLOR) + [reach])

    draft_in = random.uniform(*DRAFT_EVERY_S)
    draft_x = None
    last = utime.ticks_ms()

    while True:
        frame_start = utime.ticks_ms()
        dt = min(100, utime.ticks_diff(frame_start, last)) / 1000
        last = frame_start

        # A draft starts off one end and moves past the other.
        if draft_x is None:
            draft_in -= dt
            if draft_in <= 0:
                draft_x = -DRAFT_WIDTH
        else:
            draft_x += DRAFT_SPEED * dt
            if draft_x > COLS + DRAFT_WIDTH:
                draft_x = None
                draft_in = random.uniform(*DRAFT_EVERY_S)

        canvas.clear()
        for candle in candles:
            sway, bright, length = candle.step(dt)
            if draft_x is not None:
                d = (candle.col - draft_x) / DRAFT_WIDTH
                if -1 < d < 1:
                    push = (1 - d * d) ** 2
                    sway += DRAFT_LEAN * push
                    bright *= 1 - (1 - DRAFT_DIM) * push
            x = candle.col + sway
            wax_top = candle.wax - 0.5
            base = wax_top + WICK_GAP

            # The wax, lit from above by the flame.
            for row in range(candle.wax):
                f = (row + 1) / candle.wax
                canvas.glow(candle.col, row, wax_color,
                            bright * (WAX_GLOW[0] + (WAX_GLOW[1] - WAX_GLOW[0]) * f * f))

            c[0] = q8(x)
            c[1] = q8(base + length * 0.4)
            c[2] = q8(HALO_GLOW * bright)
            _halo(light, c, halo)

            c[1] = q8(base)
            c[2] = q8(length)
            c[3] = q8(FLAME_HEAT * bright)
            _flame(light, c, halo, palette)

        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
