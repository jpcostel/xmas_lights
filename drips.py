import math
import micropython
import random
import utime
from wiring import show_all, pixel_map
from grid import ROWS, COLS

# ============================================================
# CONFIGURATION
# ============================================================

# body:  color of the goo
# head:  glistening highlight on the leading bulb of a drip
# fade:  ms for a trail to fade to ~1/3 (longer = stickier)
LIQUIDS = [
    {"body": (30, 200, 0), "head": (160, 255, 80), "fade": 9000},    # 0: slime
    {"body": (130, 0, 0), "head": (255, 30, 15), "fade": 14000},     # 1: blood
]

FILM_DEPTH = (1.0, 1.7)        # rows of goo pooled along the top edge
FILM_HZ = (0.05, 0.15)         # how quickly the film's thickness wanders

MAX_DRIPS = 5
DRIP_EVERY_MS = (500, 2000)
START_SPEED = 0.05             # rows/sec while the drip is still bulging
ACCEL = (0.25, 0.6)            # rows/sec^2
MAX_SPEED = (0.8, 1.8)         # rows/sec
STICK_PER_SEC = 0.3            # how often a drip catches and nearly stops

PUDDLE_FADE_MS = 20000
PUDDLE_SPREAD = 0.35           # share of a landed drip that runs to each neighbor

FRAME_MS = 16                  # ~60 FPS
MAX_STEP_MS = 100              # longest single step if a frame runs late


@micropython.native
def _decay(trail, keep, dry):
    """Fade every trail cell; cells too faint to light are zeroed and skipped."""
    for line in trail:
        for c in range(len(line)):
            v = line[c]
            if v:
                v *= keep
                line[c] = v if v >= dry else 0.0


@micropython.native
def _render(pixels, trail, film, film_rows, puddle, body, dry):
    """Write the goo (trails, film along the top, puddle along the bottom)."""
    br, bg, bb = body
    last = len(trail) - 1
    for r in range(len(trail)):
        line = trail[r]
        prow = pixels[r]
        for c in range(len(line)):
            a = line[c]
            if r < film_rows:
                f = film[c] - r
                if f > a:
                    a = f if f < 1.0 else 1.0
            if r == last:
                p = puddle[c]
                if p > a:
                    a = p
            buf, ro, go, bo = prow[c]
            if a < dry:
                buf[ro] = 0
                buf[go] = 0
                buf[bo] = 0
            else:
                buf[ro] = int(br * a)
                buf[go] = int(bg * a)
                buf[bo] = int(bb * a)


class Drip:
    def __init__(self, col, depth):
        self.col = col
        self.depth = depth           # rows from the top edge to the drip's tip
        self.speed = START_SPEED
        self.accel = random.uniform(*ACCEL)
        self.max_speed = random.uniform(*MAX_SPEED)

    def update(self, dt):
        if random.random() < STICK_PER_SEC * dt:
            self.speed = START_SPEED
        self.speed = min(self.max_speed, self.speed + self.accel * dt)
        self.depth += self.speed * dt


def drip(strips, liquid=0):
    body = LIQUIDS[liquid]["body"]
    head = LIQUIDS[liquid]["head"]
    fade_ms = LIQUIDS[liquid]["fade"]

    # Grid rows here count down from the top edge: r = 0 is the top row.
    pixels = pixel_map(strips)
    pixels = [pixels[ROWS - 1 - r] for r in range(ROWS)]
    # Below this much liquid every channel rounds to 0, so skip the math.
    dry = 1.0 / max(body)
    # Only the top rows can be reached by the film.
    film_rows = int(math.ceil(FILM_DEPTH[1]))
    trail = [[0.0] * COLS for _ in range(ROWS)]
    puddle = [0.0] * COLS
    film_hz = [random.uniform(*FILM_HZ) for _ in range(COLS)]
    film_phase = [random.uniform(0, 6.283) for _ in range(COLS)]

    drips = []
    # Time is measured from scene start: the Pico's floats are single
    # precision, so raw ticks_ms() seconds get coarse after days of uptime.
    scene_start = utime.ticks_ms()
    next_drip = scene_start
    last_frame = scene_start

    while True:
        frame_start = utime.ticks_ms()
        t = utime.ticks_diff(frame_start, scene_start) / 1000
        # Step by real elapsed time, so drips ooze and trails fade at the
        # same speed whatever frame rate the Pico manages.
        step_ms = min(MAX_STEP_MS, utime.ticks_diff(frame_start, last_frame))
        last_frame = frame_start
        dt = step_ms / 1000

        # ----------------------------------------------------
        # FILM: goo pooled along the top, slowly thickening/thinning
        # ----------------------------------------------------
        film = [
            FILM_DEPTH[0] + (FILM_DEPTH[1] - FILM_DEPTH[0])
            * (0.5 + 0.5 * math.sin(2 * math.pi * film_hz[c] * t + film_phase[c]))
            for c in range(COLS)
        ]

        # ----------------------------------------------------
        # DRIPS: bulge out of the film, then ooze down
        # ----------------------------------------------------
        busy = [d.col for d in drips]
        if (len(drips) < MAX_DRIPS
                and utime.ticks_diff(frame_start, next_drip) >= 0):
            col = random.randrange(COLS)
            if col not in busy:
                drips.append(Drip(col, film[col]))
            next_drip = utime.ticks_add(frame_start, random.randint(*DRIP_EVERY_MS))

        _decay(trail, math.exp(-step_ms / fade_ms), dry)
        puddle_keep = math.exp(-step_ms / PUDDLE_FADE_MS)
        for c in range(COLS):
            puddle[c] *= puddle_keep

        heads = []                   # (row, col, highlight amount)
        falling = []
        for d in drips:
            d.update(dt)
            # Everything above the tip is wet; the tip's own cell is
            # partly filled so slow drips creep instead of hopping.
            full = min(ROWS, int(d.depth))
            for r in range(full):
                trail[r][d.col] = 1.0
            if full < ROWS:
                frac = d.depth - full
                trail[full][d.col] = max(trail[full][d.col], frac)
                heads.append((full, d.col, frac))
                if full > 0:
                    heads.append((full - 1, d.col, 1 - frac))
            if d.depth >= ROWS + 0.5:
                puddle[d.col] = min(1.0, puddle[d.col] + 1.0)
                for n in (d.col - 1, d.col + 1):
                    if 0 <= n < COLS:
                        puddle[n] = min(1.0, puddle[n] + PUDDLE_SPREAD)
            else:
                falling.append(d)
        drips = falling

        # ----------------------------------------------------
        # RENDER: the goo, then the glistening heads on top
        # ----------------------------------------------------
        _render(pixels, trail, film, film_rows, puddle, body, dry)

        for r, c, h in heads:
            if not h:
                continue
            a = trail[r][c]
            if r < film_rows:
                a = max(a, min(1.0, film[c] - r))
            if r == ROWS - 1:
                a = max(a, puddle[c])
            buf, ro, go, bo = pixels[r][c]
            buf[ro] = int(body[0] * a + (head[0] - body[0] * a) * h)
            buf[go] = int(body[1] * a + (head[1] - body[1] * a) * h)
            buf[bo] = int(body[2] * a + (head[2] - body[2] * a) * h)

        show_all(strips)

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
