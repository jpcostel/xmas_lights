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
# A bonfire in the middle of the mantle: a mound of flame, tallest in
# the center, over a bed of glowing coals. Each column's flames reach a
# height that wanders over time, and rising turbulence breaks them into
# flickering tongues that lean in toward the middle as they rise.
# Embers float up out of it and fade.

# Fire color by heat, coolest to hottest (as they'd look with gamma off).
FIRE_COLORS = [
    (0.0, (0, 0, 0)),
    (0.2, (35, 2, 0)),         # dull red, the edges of the flames
    (0.42, (160, 12, 0)),      # deep red
    (0.62, (255, 50, 0)),      # orange
    (0.8, (255, 115, 5)),      # yellow-orange
    (0.93, (255, 170, 25)),    # yellow
    (1.0, (255, 210, 80)),     # pale yellow, the hottest
]

FLAME_HEIGHT = 7.5             # rows the flames reach in the middle...
FIRE_WIDTH = 15.0              # ...falling away to nothing across this many columns
FIRE_ROUND = 1.6               # 1 = a peak, 2 = a rounded dome
LEAN_IN = 0.12                 # how much the tongues lean in toward the middle, per row
HEIGHT_SWAY = 0.3              # how much each column's height wanders, as a fraction...
HEIGHT_HZ = 0.9                # ...and how quickly
HEIGHT_WIDTH = 2.2             # columns across one rise or dip
HOT = 0.95                     # heat at the base (1 = just full yellow)
TURBULENCE = 1.6               # how far the rising turbulence pushes the heat
                               # up or down
TURB_WIDTH = 1.5               # columns across one tongue of flame
TURB_HEIGHT = 2.2              # rows from one tongue to the next above it
RISE = 3.0                     # rows/sec the turbulence climbs
DRIFT = 0.25                   # columns/sec the turbulence drifts sideways

COALS = (0.45, 0.72)           # heat of the coal bed under the fire, dimmest to brightest
COAL_WIDTH = 2.0               # columns across a brighter patch of coals...
COAL_HZ = 0.4                  # ...glowing up and down this quickly
GROUND_GLOW = 0.3              # heat of the ground just beyond the coals...
GROUND_REACH = 3.0             # ...fading out over this many columns
FLICKER = 0.12                 # quick overall flicker of the flame height
FLICKER_HZ = 3.0

EMBERS_PER_SEC = 1.2
EMBER_COLOR = (255, 110, 10)
EMBER_RISE = (1.2, 2.4)        # rows/sec
EMBER_SPREAD = 0.6             # embers start this much of the way out from the middle
EMBER_SWAY = (0.3, 0.9)        # columns
EMBER_SWAY_HZ = (0.4, 1.0)
EMBER_LIFE_S = (1.2, 2.6)
EMBER_TWINKLE_HZ = (4.0, 9.0)

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# DRAWING
# ============================================================

@micropython.viper
def _flames(light: ptr16, perm, inv_heights: ptr32, p: ptr32, palette: ptr16, coals: ptr32):
    """Fill light[] with fire. inv_heights[col] = 65536 / that column's
    flame height in rows; p holds the turbulence's scale and position
    and where the middle is; coals[col] is the heat of the bottom row
    under the flames."""
    cols = p[0]
    rows = p[1]
    sx = p[2]
    sy = p[3]
    rise = p[4]
    drift = p[5]
    hot = p[6]
    turb = p[7]
    mid = p[8]
    lean = p[9]
    o = 0
    row = 0
    while row < rows:
        # Higher up, read the turbulence from further out, so its tongues
        # draw in toward the middle as they rise.
        spread = 256 + lean * row
        col = 0
        while col < cols:
            x = mid + ((((col << 8) - mid) * spread) >> 8)
            # Two layers of turbulence, the finer one climbing faster.
            n1 = int(noise(((x * sx) >> 8) + drift, row * sy - rise, perm))
            n2 = int(noise(((x * sx) >> 7) + 30000 - drift, row * sy * 2 - rise * 2, perm))
            n = (n1 * 171 + n2 * 85) >> 8
            # Hottest at the bottom, gone at the column's flame height,
            # with the turbulence licking above it and eating into it.
            base = 256 - ((((row << 8) + 64) * inv_heights[col]) >> 16)
            heat = ((base * hot) >> 8) + (((n - 128) * turb) >> 8)
            if row == 0:
                c = coals[col]
                if heat < c:
                    heat = c
            if heat < 0:
                heat = 0
            elif heat > 255:
                heat = 255
            heat *= 3
            light[o] = palette[heat]
            light[o + 1] = palette[heat + 1]
            light[o + 2] = palette[heat + 2]
            o += 3
            col += 1
        row += 1


# ============================================================
# EMBERS
# ============================================================

class Ember:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.rise = random.uniform(*EMBER_RISE)
        self.sway = random.uniform(*EMBER_SWAY)
        self.sway_w = 2 * math.pi * random.uniform(*EMBER_SWAY_HZ)
        self.phase = random.uniform(0, 2 * math.pi)
        self.life = random.uniform(*EMBER_LIFE_S)
        self.twinkle_w = 2 * math.pi * random.uniform(*EMBER_TWINKLE_HZ)
        self.age = 0.0

    def step(self, dt):
        """Move; returns (x, y, brightness), or None once it's gone."""
        self.age += dt
        if self.age >= self.life:
            return None
        self.y += self.rise * dt
        f = self.age / self.life
        # Fades in quickly, then cools away.
        b = min(1.0, self.age * 6) * (1 - f) * (1 - f)
        b *= 0.75 + 0.25 * math.sin(self.twinkle_w * self.age + self.phase)
        x = self.x + self.sway * math.sin(self.sway_w * self.age + self.phase)
        return x, self.y, b


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def hearth_fire(strips):
    canvas = Canvas(strips)
    light = canvas.light
    palette = gradient(FIRE_COLORS)
    ember_color = to_light(EMBER_COLOR)

    # A mound of flame, tallest in the middle; none past its edges.
    mid = (COLS - 1) / 2
    half = FIRE_WIDTH / 2
    shape = [FLAME_HEIGHT * max(0.0, 1 - (abs(c - mid) / half) ** FIRE_ROUND) for c in range(COLS)]
    inv_heights = array.array("i", [0] * COLS)
    p = array.array("i", [COLS, ROWS, q8(1 / TURB_WIDTH), q8(1 / TURB_HEIGHT), 0, 0,
                          q8(HOT), q8(TURBULENCE), q8(mid), q8(LEAN_IN)])
    hx = q8(1 / HEIGHT_WIDTH)
    cx = q8(1 / COAL_WIDTH)
    coals = array.array("i", [0] * COLS)

    # Where the flames are in the noise they're drawn from.
    height_at = flicker_at = rise_at = side_at = coal_at = 0.0

    embers = []
    due = 0.0
    last = utime.ticks_ms()

    while True:
        frame_start = utime.ticks_ms()
        dt = min(100, utime.ticks_diff(frame_start, last)) / 1000
        last = frame_start
        height_at = drift(height_at, HEIGHT_HZ, dt)
        flicker_at = drift(flicker_at, FLICKER_HZ, dt)
        rise_at = drift(rise_at, RISE / TURB_HEIGHT, dt)
        side_at = drift(side_at, DRIFT / TURB_WIDTH, dt)
        coal_at = drift(coal_at, COAL_HZ, dt)

        ht = q8(height_at)
        ct = q8(coal_at)
        flicker = 1 + FLICKER * (noise(q8(flicker_at), 5000, PERM) - 128) / 128
        for c in range(COLS):
            h = shape[c] * (flicker + HEIGHT_SWAY * (noise(c * hx, ht, PERM) - 128) / 128)
            inv_heights[c] = int(65536 / max(0.15, h))
            # Coals under the fire, a faint glow on the ground past them.
            out = abs(c - mid) - half
            if out < 0:
                heat = COALS[0] + (COALS[1] - COALS[0]) * noise(c * cx, ct + 9000, PERM) / 255
            else:
                heat = GROUND_GLOW * max(0.0, 1 - out / GROUND_REACH)
            coals[c] = int(255 * heat + 0.5)
        p[4] = q8(rise_at)
        p[5] = q8(side_at)
        _flames(light, PERM, inv_heights, p, palette, coals)

        due += EMBERS_PER_SEC * dt
        while due >= 1:
            due -= 1
            x = mid + random.uniform(-1, 1) * half * EMBER_SPREAD
            embers.append(Ember(x, shape[int(x + 0.5)] * random.uniform(0.7, 1.0)))
        alive = []
        for e in embers:
            at = e.step(dt)
            if at is None or at[1] > ROWS + 1:
                continue
            canvas.glow(at[0], at[1], ember_color, at[2])
            alive.append(e)
        embers = alive

        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
