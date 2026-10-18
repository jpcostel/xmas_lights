import math
import random
import utime
from wiring import show_all
from grid import grid_to_pixel, ROWS, COLS

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
STICK_PROB = 0.01              # chance per frame a drip catches and nearly stops

PUDDLE_FADE_MS = 20000
PUDDLE_SPREAD = 0.35           # share of a landed drip that runs to each neighbor

FRAME_MS = 33                  # ~30 FPS


class Drip:
    def __init__(self, col, depth):
        self.col = col
        self.depth = depth           # rows from the top edge to the drip's tip
        self.speed = START_SPEED
        self.accel = random.uniform(*ACCEL)
        self.max_speed = random.uniform(*MAX_SPEED)

    def update(self, dt):
        if random.random() < STICK_PROB:
            self.speed = START_SPEED
        self.speed = min(self.max_speed, self.speed + self.accel * dt)
        self.depth += self.speed * dt


def drip(strips, liquid=0):
    body = LIQUIDS[liquid]["body"]
    head = LIQUIDS[liquid]["head"]
    trail_keep = math.exp(-FRAME_MS / LIQUIDS[liquid]["fade"])
    puddle_keep = math.exp(-FRAME_MS / PUDDLE_FADE_MS)
    dt = FRAME_MS / 1000

    # Grid rows here count down from the top edge: r = 0 is the top row.
    pixel = [[grid_to_pixel(ROWS - 1 - r, col) for col in range(COLS)] for r in range(ROWS)]
    trail = [[0.0] * COLS for _ in range(ROWS)]
    puddle = [0.0] * COLS
    film_hz = [random.uniform(*FILM_HZ) for _ in range(COLS)]
    film_phase = [random.uniform(0, 6.283) for _ in range(COLS)]

    drips = []
    # Time is measured from scene start: the Pico's floats are single
    # precision, so raw ticks_ms() seconds get coarse after days of uptime.
    scene_start = utime.ticks_ms()
    next_drip = scene_start

    while True:
        frame_start = utime.ticks_ms()
        t = utime.ticks_diff(frame_start, scene_start) / 1000

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

        for r in range(ROWS):
            line = trail[r]
            for c in range(COLS):
                line[c] *= trail_keep
        for c in range(COLS):
            puddle[c] *= puddle_keep

        heads = {}
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
                heads[(full, d.col)] = frac
                if full > 0:
                    heads[(full - 1, d.col)] = max(heads.get((full - 1, d.col), 0.0), 1 - frac)
            if d.depth >= ROWS + 0.5:
                puddle[d.col] = min(1.0, puddle[d.col] + 1.0)
                for n in (d.col - 1, d.col + 1):
                    if 0 <= n < COLS:
                        puddle[n] = min(1.0, puddle[n] + PUDDLE_SPREAD)
            else:
                falling.append(d)
        drips = falling

        # ----------------------------------------------------
        # RENDER
        # ----------------------------------------------------
        for r in range(ROWS):
            line = trail[r]
            for c in range(COLS):
                a = line[c]
                f = film[c] - r
                if f > a:
                    a = min(1.0, f)
                if r == ROWS - 1 and puddle[c] > a:
                    a = puddle[c]
                color = (body[0] * a, body[1] * a, body[2] * a)
                h = heads.get((r, c))
                if h:
                    color = (
                        color[0] + (head[0] - color[0]) * h,
                        color[1] + (head[1] - color[1]) * h,
                        color[2] + (head[2] - color[2]) * h,
                    )
                strand, index = pixel[r][c]
                strips[strand][index] = (int(color[0]), int(color[1]), int(color[2]))

        show_all(strips)

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
