import math
import random
import utime
from wiring import show_all, pixel_map, snapshot, restore
from grid import ROWS, COLS

# ============================================================
# CONFIGURATION
# ============================================================

# Dusk gradient the bats are silhouetted against, bottom to top.
SKY_BOTTOM = (255, 80, 0)
SKY_MIDDLE = (150, 0, 90)
SKY_TOP = (40, 0, 90)          # bright enough that bats still show at the top

WAVE_SIZE = (5, 10)            # bats per swarm
WAVE_SPAWN_MS = (450, 1000)    # gap between bats within a swarm
WAVE_GAP_MS = (1500, 5000)     # quiet time between swarms
BAT_SPEED = (5.0, 9.0)         # columns per second, picked per swarm...
BAT_SPEED_JITTER = 0.4         # ...+/- this per bat, so they fly together
                               # instead of overtaking into black blobs
MIN_ROW_CHANGE = 2             # consecutive bats this many rows apart
FLAP_HZ = (3.0, 5.0)           # full wing beats per second
WOBBLE = 0.7                   # rows of up/down drift
WOBBLE_HZ = (0.4, 1.0)

FRAME_MS = 16                  # ~60 FPS

# Wings up / wings down (ears showing), drawn top row first.
BAT_FRAMES = [
    [
        "##...##",
        ".##.##.",
        "...#...",
    ],
    [
        "..#.#..",
        ".#####.",
        "##...##",
    ],
]
BAT_WIDTH = 7


def _frame_cells(frame):
    """(dx, dy) offsets of a bat frame's pixels, dy measured up from its bottom row."""
    cells = []
    h = len(frame)
    for r, line in enumerate(frame):
        for c, ch in enumerate(line):
            if ch == "#":
                cells.append((c, h - 1 - r))
    return cells


FRAME_CELLS = [_frame_cells(f) for f in BAT_FRAMES]


class Bat:
    def __init__(self, direction, speed, row, now_ms):
        self.direction = direction
        self.start_ms = now_ms
        self.speed = speed + random.uniform(-BAT_SPEED_JITTER, BAT_SPEED_JITTER)
        self.row = row
        self.flap_hz = random.uniform(*FLAP_HZ)
        self.flap_phase = random.uniform(0, 1)
        self.wobble_hz = random.uniform(*WOBBLE_HZ)
        self.wobble_phase = random.uniform(0, 6.283)

    def position(self, now_ms):
        age = utime.ticks_diff(now_ms, self.start_ms) / 1000
        travel = age * self.speed
        x = -BAT_WIDTH + travel if self.direction > 0 else COLS - travel
        y = self.row + WOBBLE * math.sin(2 * math.pi * self.wobble_hz * age + self.wobble_phase)
        frame = int((age * self.flap_hz + self.flap_phase) * 2) % 2
        return x, y, frame

    def gone(self, x):
        return x > COLS or x < -BAT_WIDTH


def _sky():
    sky = []
    for row in range(ROWS):
        t = row / (ROWS - 1)
        if t < 0.5:
            a, b, f = SKY_BOTTOM, SKY_MIDDLE, t / 0.5
        else:
            a, b, f = SKY_MIDDLE, SKY_TOP, (t - 0.5) / 0.5
        sky.append((
            int(a[0] + (b[0] - a[0]) * f),
            int(a[1] + (b[1] - a[1]) * f),
            int(a[2] + (b[2] - a[2]) * f),
        ))
    return sky


def bat_swarm(strips):
    pixels = pixel_map(strips)

    # The sky never changes: draw it once and copy the bytes back at the
    # start of each frame, then draw the bats on top.
    sky = _sky()
    for row in range(ROWS):
        s = sky[row]
        for col in range(COLS):
            buf, ro, go, bo = pixels[row][col]
            buf[ro] = s[0]
            buf[go] = s[1]
            buf[bo] = s[2]
    background = snapshot(strips)

    bats = []
    now = utime.ticks_ms()
    to_spawn = 0
    direction = 1
    speed = BAT_SPEED[0]
    last_row = -MIN_ROW_CHANGE
    next_spawn = now
    next_wave = now

    while True:
        frame_start = utime.ticks_ms()

        # ----------------------------------------------------
        # SWARMS: a burst of bats, then a pause
        # ----------------------------------------------------
        if to_spawn == 0 and utime.ticks_diff(frame_start, next_wave) >= 0:
            to_spawn = random.randint(*WAVE_SIZE)
            direction = random.choice((1, -1))
            speed = random.uniform(*BAT_SPEED)
            next_spawn = frame_start

        if to_spawn > 0 and utime.ticks_diff(frame_start, next_spawn) >= 0:
            rows = [r for r in range(ROWS - len(BAT_FRAMES[0]) + 1)
                    if abs(r - last_row) >= MIN_ROW_CHANGE]
            last_row = random.choice(rows)
            bats.append(Bat(direction, speed, last_row, frame_start))
            to_spawn -= 1
            next_spawn = utime.ticks_add(frame_start, random.randint(*WAVE_SPAWN_MS))
            if to_spawn == 0:
                next_wave = utime.ticks_add(frame_start, random.randint(*WAVE_GAP_MS))

        # ----------------------------------------------------
        # SKY, THEN BAT SILHOUETTES
        # ----------------------------------------------------
        # Bats snap to whole cells: blending across columns would smooth
        # the motion but smear their one-pixel wing tips into grey.
        restore(strips, background)

        alive = []
        for bat in bats:
            x, y, frame = bat.position(frame_start)
            if bat.gone(x):
                continue
            alive.append(bat)
            x0 = int(round(x))
            y0 = int(round(y))
            for dx, dy in FRAME_CELLS[frame]:
                col = x0 + dx
                row = y0 + dy
                if 0 <= col < COLS and 0 <= row < ROWS:
                    buf, ro, go, bo = pixels[row][col]
                    buf[ro] = 0
                    buf[go] = 0
                    buf[bo] = 0
        bats = alive

        show_all(strips)

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
