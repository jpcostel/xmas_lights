import math
import micropython
import random
import utime
from wiring import show_all, pixel_map, restore
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
LEAF_BRIGHTNESS = (0.7, 1.0)   # per-leaf variation

LEAVES_PER_SEC = 1.4
MAX_FALLING = 14
FALL_SPEED = (0.9, 1.6)        # rows/sec, averaged over a swing
SWAY = (0.7, 1.8)              # columns either side of a leaf's path
SWAY_HZ = (0.2, 0.4)           # full side-to-side swings per second
FLUTTER_HZ = (0.4, 1.2)        # how fast a leaf turns over
FLUTTER_DEPTH = 0.45           # how much it dims when edge-on

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
REST_BRIGHTNESS = 0.85

FRAME_MS = 16                  # ~60 FPS
MAX_STEP_MS = 100              # longest single step if a frame runs late


# ============================================================
# DRAWING
# ============================================================

@micropython.native
def _draw_leaf(pixels, x, y, r, g, b):
    """Add a leaf at a fractional grid position, blended across the up to
    four LEDs around it so it glides instead of hopping.

    Plain bilinear blending dims a leaf that sits between LEDs, and
    scaling it back up to full brightness makes it swell to a 2x2 block;
    dividing by the square root of the peak weight is the middle ground.
    The peak ignores the grid edges, so a leaf half off the edge fades.
    """
    x0 = int(math.floor(x))
    y0 = int(math.floor(y))
    fx = x - x0
    fy = y - y0
    peak = (fx if fx > 0.5 else 1 - fx) * (fy if fy > 0.5 else 1 - fy)
    gain = 1 / math.sqrt(peak)
    for dy in (0, 1):
        row = y0 + dy
        if row < 0 or row >= ROWS:
            continue
        wy = fy if dy else 1 - fy
        line = pixels[row]
        for dx in (0, 1):
            col = x0 + dx
            if col < 0 or col >= COLS:
                continue
            w = (fx if dx else 1 - fx) * wy * gain
            if w <= 0:
                continue
            buf, ro, go, bo = line[col]
            v = buf[ro] + int(r * w)
            buf[ro] = v if v < 255 else 255
            v = buf[go] + int(g * w)
            buf[go] = v if v < 255 else 255
            v = buf[bo] + int(b * w)
            buf[bo] = v if v < 255 else 255


# ============================================================
# LEAVES
# ============================================================

class Leaf:
    def __init__(self, x):
        self.x = x                       # center of its swing
        self.y = ROWS + random.uniform(0.2, 1.0)   # starts just above the top
        c = random.choice(LEAF_COLORS)
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
                falling.append(Leaf(random.uniform(-1.0, COLS) - wind * 3))

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
            _draw_leaf(pixels, leaf.x, leaf.y, c[0] * b, c[1] * b, c[2] * b)

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
                _draw_leaf(pixels, x, landed.y, c[0] * b, c[1] * b, c[2] * b)
                continue
            if leaf.y < -1.0 or x < -2.0 or x > COLS + 1.0:
                continue
            _draw_leaf(pixels, x, leaf.y, c[0] * b, c[1] * b, c[2] * b)
            still.append(leaf)
        falling = still

        show_all(strips)

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
