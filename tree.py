import array
import micropython
import random
import utime
from canvas import Canvas, PERM, LIGHT, noise, q8, to_light
from grid import ROWS, COLS
from shapes import Polygon

# ============================================================
# CONFIGURATION
# ============================================================
# A Christmas tree: three green tiers on a trunk, a star on top that
# glows and now and then sparkles, and strings of lights running down
# it in diagonal lines. White lights twinkle softly; colored lights
# step their colors along the string, fading from one to the next.
#
# Positions are in LED spacings: x = column, y = row (0 = bottom).
# Colors are as they'd look with gamma off.

GREEN = (0, 40, 6)             # dim, so the lights stand out
TRUNK = (45, 16, 0)
TIERS = [                      # (bottom left, bottom right, top), bottom tier first
    ((4.6, 0.6), (19.4, 0.6), (12.0, 4.6)),
    ((6.6, 2.5), (17.4, 2.5), (12.0, 6.3)),
    ((8.6, 4.3), (15.4, 4.3), (12.0, 7.4)),
]
TRUNK_AT = [(10.6, -0.6), (13.4, -0.6), (13.4, 0.5), (10.6, 0.5)]

STAR = (12, 7)                 # the LED at the top
STAR_COLOR = (255, 190, 40)
STAR_GLOW = (0.55, 1.0)        # dimmest and brightest as it pulses...
STAR_PULSE_HZ = 0.25
SPARKLES_PER_MIN = 8           # ...and sparkles this often
SPARKLE_S = 0.6
SPARKLE_WHITE = 120            # a sparkle whitens the star this much (0-255)
RAYS = 0.45                    # sparkle light on the LEDs around the star

# Lights: on LEDs inside the tree where (col + LIGHT_SLANT * row) % LIGHT_EVERY == 0,
# making diagonal strings; LEDs this close to an edge are left out.
LIGHT_EVERY = 3
LIGHT_SLANT = 2
LIGHT_EDGE = 0.35

WARM_WHITE = (255, 190, 110)
WHITE_LEVEL = (0.25, 1.0)      # twinkling between these
TWINKLE_HZ = 0.7

COLORS = [                     # around the string, no green: it'd vanish on the tree
    (255, 0, 0),               # red
    (255, 140, 0),             # gold
    (0, 40, 255),              # blue
    (200, 0, 160),             # magenta
    (255, 60, 0),              # orange
    (0, 160, 160),             # teal
    (220, 200, 180),           # white
]
COLOR_LEVEL = 0.85
COLOR_TWINKLE = 0.25           # gentle twinkle on top
STEP_S = 1.2                   # each light moves on to the next color this often...
FADE_S = 0.5                   # ...dimming out of one and back up into the next

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# DRAWING
# ============================================================

@micropython.viper
def _lights(light: ptr16, spots: ptr32, n: int):
    """Set n lights: spots holds (light index, r, g, b) for each."""
    i = 0
    while i < n * 4:
        o = spots[i + 0]
        light[o + 0] = spots[i + 1]
        light[o + 1] = spots[i + 2]
        light[o + 2] = spots[i + 3]
        i += 4


@micropython.viper
def _add(light: ptr16, o: int, r: int, g: int, b: int):
    # Indexed by o + 0, never plain o: see VIPER_PTR16_BUG in canvas.py.
    top = 255 * 16
    v = int(light[o + 0]) + r
    light[o + 0] = v if v < top else top
    v = int(light[o + 1]) + g
    light[o + 1] = v if v < top else top
    v = int(light[o + 2]) + b
    light[o + 2] = v if v < top else top


def _inside(x, y, tri):
    """How far (x, y) is inside a triangle, in LED spacings (< 0 outside)."""
    (ax, ay), (bx, by), (cx, cy) = tri
    best = 99.0
    for (px, py), (qx, qy) in (((ax, ay), (bx, by)), ((bx, by), (cx, cy)), ((cx, cy), (ax, ay))):
        nx, ny = py - qy, qx - px
        length = (nx * nx + ny * ny) ** 0.5
        d = (nx * (x - px) + ny * (y - py)) / length
        # Same side as the triangle's middle counts as inside.
        mx = (ax + bx + cx) / 3
        my = (ay + by + cy) / 3
        if nx * (mx - px) + ny * (my - py) < 0:
            d = -d
        best = min(best, d)
    return best


def _string():
    """The lights' LEDs, in order along the strings: bottom row first,
    each row left to right."""
    spots = []
    for row in range(ROWS):
        for col in range(COLS):
            if (col, row) == STAR or (col + LIGHT_SLANT * row) % LIGHT_EVERY:
                continue
            if max(_inside(col, row, tri) for tri in TIERS) >= LIGHT_EDGE:
                spots.append((col, row))
    return spots


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def christmas_tree(strips, colorful=False):
    canvas = Canvas(strips)
    light = canvas.light

    # The tree doesn't move: paint it once and copy it in each frame.
    for points in TIERS:
        Polygon(GREEN, list(points), sides=3).draw(light)
    Polygon(TRUNK, TRUNK_AT).draw(light)
    tree = array.array("H", light)

    string = _string()
    n = len(string)
    spots = array.array("i", [0] * (n * 4))
    for i, (col, row) in enumerate(string):
        spots[i * 4] = 3 * (row * COLS + col)
    warm = to_light(WARM_WHITE)
    colors = [to_light(c) for c in COLORS]
    star_o = 3 * (STAR[1] * COLS + STAR[0])
    star = to_light(STAR_COLOR)
    rays = [3 * (r * COLS + c) for c, r in ((STAR[0] - 1, STAR[1]), (STAR[0] + 1, STAR[1]),
                                              (STAR[0], STAR[1] - 1))]

    scene_start = utime.ticks_ms()
    sparkle_at = -1.0
    last_t = 0.0

    while True:
        frame_start = utime.ticks_ms()
        t = utime.ticks_diff(frame_start, scene_start) / 1000
        dt = min(0.1, t - last_t)
        last_t = t
        light[:] = tree

        tq = q8(t * TWINKLE_HZ % 256)
        if colorful:
            step = int(t / STEP_S)
            fade = min(1.0, (t - step * STEP_S) / FADE_S)
        for i in range(n):
            # Each light twinkles on its own stretch of the noise.
            tw = noise(tq, i * 2560 + 7000, PERM) / 255
            if colorful:
                # Through dark, not straight across: red to teal would
                # pass through grey.
                if fade < 0.5:
                    color = colors[(i + step - 1) % len(colors)]
                    dim = 1 - 2 * fade
                else:
                    color = colors[(i + step) % len(colors)]
                    dim = 2 * fade - 1
                k = COLOR_LEVEL * dim * (1 - COLOR_TWINKLE + COLOR_TWINKLE * tw)
                c = [int(x * k) for x in color]
            else:
                k = WHITE_LEVEL[0] + (WHITE_LEVEL[1] - WHITE_LEVEL[0]) * tw * tw
                c = [int(x * k) for x in warm]
            spots[i * 4 + 1], spots[i * 4 + 2], spots[i * 4 + 3] = c
        _lights(light, spots, n)

        # The star: a slow pulse, and now and then a sparkle that lights
        # the LEDs around it.
        pulse = 0.5 + 0.5 * noise(q8(t * STAR_PULSE_HZ % 256), 3000, PERM) / 255
        k = STAR_GLOW[0] + (STAR_GLOW[1] - STAR_GLOW[0]) * pulse
        if sparkle_at < 0 and random.random() < SPARKLES_PER_MIN / 60 * dt:
            sparkle_at = t
        burst = 0.0
        if sparkle_at >= 0:
            g = (t - sparkle_at) / SPARKLE_S
            if g >= 1:
                sparkle_at = -1.0
            else:
                burst = 1 - g
        k = min(1.0, k + burst)
        white = LIGHT * SPARKLE_WHITE * burst
        for ch in range(3):
            light[star_o + ch] = min(255 * LIGHT, int(star[ch] * k + white))
        for o in rays:
            _add(light, o, int(star[0] * RAYS * burst), int(star[1] * RAYS * burst), int(star[2] * RAYS * burst))
        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
