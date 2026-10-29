import math
import random
import utime
from wiring import show_all, pixel_map, snapshot, restore
from grid import ROWS, COLS

# ============================================================
# CONFIGURATION
# ============================================================

SKY_COLOR = (0, 2, 14)
GLOW_COLOR = (12, 16, 45)      # sky brightens toward this right around the moon
GLOW_RADIUS = 3.0              # cells beyond the moon's edge the glow reaches

MOON_COLOR = (255, 214, 140)
MOON_CENTER = (12.0, 3.5)      # (col, row)
MOON_RADIUS = 5.5              # taller than the grid; the top and bottom are
                               # clipped so there's more moon to fly across
CRATERS = (                    # (col, row, shade)
    (9, 5, 0.72),
    (10, 4, 0.85),
    (15, 2, 0.75),
    (14, 6, 0.85),
    (11, 1, 0.82),
)

STAR_COLOR = (150, 150, 170)
NUM_STARS = 9
STAR_TWINKLE_HZ = (0.3, 1.2)

WITCH_EVERY_MS = (6000, 20000) # gap between fly-bys
WITCH_SPEED = 5.0              # columns per second
WITCH_BOB = 0.6                # rows of up/down drift while flying
WITCH_BOB_HZ = 0.5

FRAME_MS = 16                  # ~60 FPS

# Witch on a broom, facing right (flipped when flying left): pointy hat,
# a long broom handle out front, and bristles flaring behind. At 8 rows
# tall the separate parts matter more than the body for reading as a witch.
# Drawn top row first; '#' is witch, '.' is transparent.
WITCH = [
    "....#........",
    "....##.......",
    "...####......",
    "#...##.......",
    "#############",
    "#............",
]


# ============================================================
# SCENE
# ============================================================

def _lerp(a, b, t):
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def _sky_and_moon():
    """Static background: sky, glow around the moon, the moon and craters."""
    craters = {(c, r): s for c, r, s in CRATERS}
    bg = []
    for row in range(ROWS):
        line = []
        for col in range(COLS):
            d = math.sqrt((col - MOON_CENTER[0]) ** 2 + (row - MOON_CENTER[1]) ** 2)
            glow = max(0.0, 1.0 - (d - MOON_RADIUS) / GLOW_RADIUS)
            sky = _lerp(SKY_COLOR, GLOW_COLOR, min(1.0, glow))
            # Soft edge so the moon looks round rather than blocky.
            coverage = min(1.0, max(0.0, MOON_RADIUS + 0.5 - d))
            moon = MOON_COLOR
            if (col, row) in craters:
                moon = _lerp((0, 0, 0), MOON_COLOR, craters[(col, row)])
            c = _lerp(sky, moon, coverage)
            line.append((int(c[0]), int(c[1]), int(c[2])))
        bg.append(line)
    return bg


def _place_stars():
    stars = []
    while len(stars) < NUM_STARS:
        col = random.randrange(COLS)
        row = random.randrange(ROWS)
        d = math.sqrt((col - MOON_CENTER[0]) ** 2 + (row - MOON_CENTER[1]) ** 2)
        if d > MOON_RADIUS + GLOW_RADIUS * 0.6 and (col, row) not in [s[:2] for s in stars]:
            stars.append((col, row, random.uniform(*STAR_TWINKLE_HZ), random.uniform(0, 6.283)))
    return stars


def _witch_cells(direction):
    """(dx, dy) offsets of the witch's pixels, dy measured up from her bottom row."""
    cells = []
    h = len(WITCH)
    w = len(WITCH[0])
    for r, line in enumerate(WITCH):
        for c, ch in enumerate(line):
            if ch == "#":
                # Mirror by column rather than line[::-1]: MicroPython
                # doesn't support slices with a negative step.
                cells.append((c if direction > 0 else w - 1 - c, h - 1 - r))
    return cells


def moon_witch(strips):
    stars = _place_stars()
    pixels = pixel_map(strips)

    # Sky and moon never change: draw them once and copy the bytes back
    # at the start of each frame, then draw stars and witch on top.
    bg = _sky_and_moon()
    for row in range(ROWS):
        for col in range(COLS):
            buf, ro, go, bo = pixels[row][col]
            c = bg[row][col]
            buf[ro] = c[0]
            buf[go] = c[1]
            buf[bo] = c[2]
    background = snapshot(strips)

    witch_w = len(WITCH[0])
    witch_h = len(WITCH)
    witch = None   # (start_ms, direction, cells) while flying
    # Time is measured from scene start: the Pico's floats are single
    # precision, so raw ticks_ms() seconds get coarse after days of uptime.
    scene_start = utime.ticks_ms()
    next_witch = utime.ticks_add(scene_start, random.randint(2000, 5000))

    while True:
        frame_start = utime.ticks_ms()
        t = utime.ticks_diff(frame_start, scene_start) / 1000

        # ----------------------------------------------------
        # BACKGROUND + TWINKLING STARS
        # ----------------------------------------------------
        restore(strips, background)

        for col, row, hz, phase in stars:
            b = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(2 * math.pi * hz * t + phase))
            buf, ro, go, bo = pixels[row][col]
            buf[ro] = int(STAR_COLOR[0] * b)
            buf[go] = int(STAR_COLOR[1] * b)
            buf[bo] = int(STAR_COLOR[2] * b)

        # ----------------------------------------------------
        # WITCH: an occasional silhouette fly-by
        # ----------------------------------------------------
        if witch is None and utime.ticks_diff(frame_start, next_witch) >= 0:
            direction = random.choice((1, -1))
            witch = (frame_start, direction, _witch_cells(direction))

        if witch is not None:
            start, direction, cells = witch
            age = utime.ticks_diff(frame_start, start) / 1000
            travel = int(age * WITCH_SPEED)
            x = -witch_w + travel if direction > 0 else COLS - travel
            bob = WITCH_BOB * math.sin(2 * math.pi * WITCH_BOB_HZ * age)
            y = int(round(MOON_CENTER[1] - (witch_h - 1) / 2 + bob))

            if x > COLS or x < -witch_w:
                witch = None
                next_witch = utime.ticks_add(frame_start, random.randint(*WITCH_EVERY_MS))
            else:
                for dx, dy in cells:
                    col = x + dx
                    row = y + dy
                    if 0 <= col < COLS and 0 <= row < ROWS:
                        buf, ro, go, bo = pixels[row][col]
                        buf[ro] = 0
                        buf[go] = 0
                        buf[bo] = 0

        show_all(strips)

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
