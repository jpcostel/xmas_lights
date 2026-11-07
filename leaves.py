import math
import micropython
import random
import utime
import wiring
from wiring import show_all, pixel_map, restore, true_color
from grid import ROWS, COLS

# ============================================================
# CONFIGURATION
# ============================================================

LEAF_COLORS = [
    (220, 25, 0),      # crimson
    (255, 55, 0),      # red-orange
    (255, 95, 0),      # orange
    (255, 150, 0),     # amber
    (200, 170, 10),    # gold
    (130, 40, 0),      # brown
]
# Brightness values below are as perceived (show_all applies gamma).
LEAF_BRIGHTNESS = (0.85, 1.0)  # per-leaf variation

LEAVES_PER_SEC = 1.4
MAX_FALLING = 14
FALL_SPEED = (0.9, 1.6)        # rows/sec, averaged over a swing
SWAY = (0.7, 1.8)              # columns either side of a leaf's path
SWAY_HZ = (0.2, 0.4)           # full side-to-side swings per second
FLUTTER_HZ = (0.4, 1.2)        # how fast a leaf turns over
FLUTTER_DEPTH = 0.25           # how much it dims when edge-on

WIND = 0.5                     # columns/sec of slowly wandering breeze
WIND_PERIOD_S = 23
GUST = (0.6, 1.2)              # extra columns/sec at a gust's peak
GUST_EVERY_MS = (8000, 20000)
GUST_MS = 3000

PILE_ROWS = 2                  # how high leaves stack at the bottom
REST_MS = (4000, 8000)         # how long a landed leaf lingers...
REST_FADE_MS = 2500            # ...before fading away over this long
SETTLE_SPEED = 2.0             # rows/sec a resting leaf slides down
LAND_BLEND_MS = 400            # ease from fluttering to resting brightness
REST_BRIGHTNESS = 0.93

# How far a leaf's light reaches, in LED spacings, sideways and up/down.
# Wider than tall makes a flat leaf. Keep LEAF_HEIGHT at 0.8 or more:
# smaller makes hand-offs between rows jerky, and below ~0.6 a leaf can
# vanish between LEDs.
LEAF_WIDTH = 2.0
LEAF_HEIGHT = 0.8
LEAF_CURL = 0.5                # rows the leaf rises one LED out from its middle,
                               # so its edges curl up (0 = flat, negative = droop)

FRAME_MS = 16                  # ~60 FPS
MAX_STEP_MS = 100              # longest single step if a frame runs late


# ============================================================
# DRAWING
# ============================================================

@micropython.native
def _draw_leaf(pixels, x, y, r, g, b, width, height, curl, inv_gamma):
    """Light the LEDs near a leaf by how close each one is to it.

    The leaf is a point that moves anywhere on the grid, not just from LED
    to LED. Every LED inside an ellipse `width` across and `height` high
    (half-widths, in LED spacings) around it gets a share of its light
    that falls smoothly from full at the leaf to nothing at the ellipse's
    edge: (1 - d^2)^2, with d measured relative to the ellipse, which has
    no corners, so motion never jerks. The ellipse is bent so its middle
    line rises by `curl` * (sideways distance)^2: the edges curl up.

    The shares are made to add up to the leaf's full light in real light
    output, then raised to 1/gamma so show_all's gamma correction turns
    them back. The leaf gives off the same light wherever it is, and
    dithering lets the faint glow on the LEDs it's heading toward rise in
    fine steps. LEDs past the grid's edge still take their share, so a
    leaf fades as it drifts off.
    """
    inv_w2 = 1.0 / (width * width)
    inv_h2 = 1.0 / (height * height)
    x_lo = int(math.floor(x - width))
    x_hi = int(math.ceil(x + width))
    rise = curl * width * width        # how far the tips are bent
    y_lo = int(math.floor(y - height + (rise if rise < 0.0 else 0.0)))
    y_hi = int(math.ceil(y + height + (rise if rise > 0.0 else 0.0)))
    total = 0.0
    near = []
    for row in range(y_lo, y_hi + 1):
        for col in range(x_lo, x_hi + 1):
            ox = col - x
            oy = row - y - curl * ox * ox   # measured from the bent middle line
            d2 = ox * ox * inv_w2 + oy * oy * inv_h2
            if d2 >= 1.0:
                continue
            f = 1.0 - d2
            f *= f
            total += f
            if 0 <= row < ROWS and 0 <= col < COLS:
                near.append((row, col, f))
    if total <= 0.0:
        return
    for row, col, f in near:
        k = (f / total) ** inv_gamma
        buf, ro, go, bo = pixels[row][col]
        v = buf[ro] + int(r * k)
        buf[ro] = v if v < 255 else 255
        v = buf[go] + int(g * k)
        buf[go] = v if v < 255 else 255
        v = buf[bo] + int(b * k)
        buf[bo] = v if v < 255 else 255


# ============================================================
# LEAVES
# ============================================================

class Leaf:
    def __init__(self, x, colors):
        self.x = x                       # center of its swing
        self.y = ROWS + random.uniform(0.2, 1.0)   # starts just above the top
        c = random.choice(colors)
        k = random.uniform(*LEAF_BRIGHTNESS)
        self.color = (c[0] * k, c[1] * k, c[2] * k)
        self.fall = random.uniform(*FALL_SPEED)
        self.sway = random.uniform(*SWAY)
        self.sway_w = 2 * math.pi * random.uniform(*SWAY_HZ)
        self.sway_phase = random.uniform(0, 2 * math.pi)
        self.flutter_w = 2 * math.pi * random.uniform(*FLUTTER_HZ)
        self.flutter_phase = random.uniform(0, 2 * math.pi)
        self.age = 0.0

    def step(self, dt, wind):
        self.age += dt
        angle = self.sway_w * self.age + self.sway_phase
        # Pendulum: quickest through the middle of a swing, hanging at
        # the ends. The 0.5 + 0.8|cos| profile averages ~1.0.
        self.y -= self.fall * (0.5 + 0.8 * abs(math.cos(angle))) * dt
        self.x += wind * dt
        return self.x + self.sway * math.sin(angle)

    def brightness(self):
        turn = abs(math.cos(self.flutter_w * self.age + self.flutter_phase))
        return 1 - FLUTTER_DEPTH * (1 - turn)


class Resting:
    """A leaf that has landed in the pile at the bottom."""

    def __init__(self, col, x, y, color, brightness, now_ms):
        self.col = col
        self.x = x                       # eases onto col after landing
        self.y = y
        self.color = color
        self.landed_ms = now_ms
        self.land_brightness = brightness
        self.life_ms = random.randint(*REST_MS) + REST_FADE_MS

    def brightness(self, now_ms):
        age = utime.ticks_diff(now_ms, self.landed_ms)
        if age >= self.life_ms:
            return 0.0
        b = REST_BRIGHTNESS
        if age < LAND_BLEND_MS:
            t = age / LAND_BLEND_MS
            b = self.land_brightness + (REST_BRIGHTNESS - self.land_brightness) * t
        fade_left = self.life_ms - age
        if fade_left < REST_FADE_MS:
            t = fade_left / REST_FADE_MS
            b *= t * t * (3 - 2 * t)
        return b


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def falling_leaves(strips):
    pixels = pixel_map(strips)
    blank = [bytes(len(s.buf)) for s in strips]
    colors = [true_color(c) for c in LEAF_COLORS]
    inv_gamma = 1 / wiring.GAMMA
    width = LEAF_WIDTH
    height = LEAF_HEIGHT
    curl = LEAF_CURL

    falling = []
    resting = []
    due = 0.0
    gust_start = None
    gust_peak = 0.0

    scene_start = utime.ticks_ms()
    last_frame = scene_start
    next_gust = utime.ticks_add(scene_start, random.randint(*GUST_EVERY_MS))

    while True:
        frame_start = utime.ticks_ms()
        step_ms = min(MAX_STEP_MS, utime.ticks_diff(frame_start, last_frame))
        last_frame = frame_start
        dt = step_ms / 1000
        # Time is measured from scene start: the Pico's floats are single
        # precision, so raw ticks_ms() seconds get coarse after days of uptime.
        t = utime.ticks_diff(frame_start, scene_start) / 1000

        # ----------------------------------------------------
        # WIND: a slow wandering breeze plus the odd gust
        # ----------------------------------------------------
        wind = WIND * math.sin(2 * math.pi * t / WIND_PERIOD_S)
        if gust_start is None and utime.ticks_diff(frame_start, next_gust) >= 0:
            gust_start = frame_start
            gust_peak = random.uniform(*GUST) * random.choice((1, -1))
        if gust_start is not None:
            g = utime.ticks_diff(frame_start, gust_start) / GUST_MS
            if g >= 1:
                gust_start = None
                next_gust = utime.ticks_add(frame_start, random.randint(*GUST_EVERY_MS))
            else:
                wind += gust_peak * math.sin(math.pi * g)

        # ----------------------------------------------------
        # SPAWN: new leaves drift in across the top, a little upwind
        # ----------------------------------------------------
        due += LEAVES_PER_SEC * dt
        while due >= 1:
            due -= 1
            if len(falling) < MAX_FALLING:
                falling.append(Leaf(random.uniform(-1.0, COLS) - wind * 3, colors))

        # ----------------------------------------------------
        # PILE: how high the resting leaves are stacked per column
        # ----------------------------------------------------
        alive = []
        stack = [0] * COLS
        for leaf in resting:
            if utime.ticks_diff(frame_start, leaf.landed_ms) >= leaf.life_ms:
                continue
            # Ease down into any gap left by a faded leaf below, and
            # sideways onto the LED it landed nearest.
            target = stack[leaf.col]
            stack[leaf.col] += 1
            if leaf.y > target:
                leaf.y = max(target, leaf.y - SETTLE_SPEED * dt)
            if leaf.x != leaf.col:
                step = SETTLE_SPEED * dt
                off = leaf.col - leaf.x
                leaf.x = leaf.col if abs(off) <= step else leaf.x + (step if off > 0 else -step)
            alive.append(leaf)
        resting = alive

        restore(strips, blank)

        for leaf in resting:
            b = leaf.brightness(frame_start)
            c = leaf.color
            _draw_leaf(pixels, leaf.x, leaf.y, c[0] * b, c[1] * b, c[2] * b, width, height, curl, inv_gamma)

        # ----------------------------------------------------
        # FALLING LEAVES
        # ----------------------------------------------------
        still = []
        for leaf in falling:
            x = leaf.step(dt, wind)
            col = int(round(x))
            b = leaf.brightness()
            c = leaf.color
            # Land only when arriving at the top of the pile from above; a
            # leaf that already fell past a full column keeps falling rather
            # than popping back up when space opens below it.
            if (0 <= col < COLS and stack[col] < PILE_ROWS
                    and stack[col] - 0.5 < leaf.y <= stack[col]):
                landed = Resting(col, x, float(stack[col]), c, b, frame_start)
                resting.append(landed)
                stack[col] += 1
                # Draw it this frame too, or it blinks out as it lands.
                _draw_leaf(pixels, x, landed.y, c[0] * b, c[1] * b, c[2] * b, width, height, curl, inv_gamma)
                continue
            if leaf.y < -1.0 or x < -2.0 or x > COLS + 1.0:
                continue
            _draw_leaf(pixels, x, leaf.y, c[0] * b, c[1] * b, c[2] * b, width, height, curl, inv_gamma)
            still.append(leaf)
        falling = still

        show_all(strips)

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
