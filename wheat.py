import array
import math
import micropython
import random
import utime
from canvas import Canvas, PERM, drift, noise, q8, to_light
from grid import ROWS, COLS

# ============================================================
# CONFIGURATION
# ============================================================
# A field of wheat at sunset: golden stalks sway gently, and gusts of
# wind roll across the field, bending them over and catching the light
# as they go. Each stalk is a little spring, so it overshoots and
# settles after a gust has passed.

STEM_COLOR = (65, 34, 3)       # the stalks (as they'd look with gamma off)...
HEAD_COLOR = (255, 170, 35)    # ...and the ears of grain at the top
BACK_SHADE = 0.3               # the row of stalks behind, this bright
SKY = [                        # background, bottom row first
    (10, 3, 0),                # earth
    (4, 1, 0),
    (3, 1, 0),
    (3, 1, 1),
    (5, 1, 2),
    (8, 2, 3),
    (12, 3, 4),                # a faint dusky glow at the top
    (16, 5, 4),
]

STALKS = 13                    # in front, spread across the mantle...
BACK_STALKS = 12               # ...and behind, between them
HEIGHT = (4.6, 6.8)            # rows, front stalks (the back ones are a little shorter)
STEM_WIDTH = 0.55              # columns
HEAD_WIDTH = 0.9
HEAD_LENGTH = 1.8              # rows of grain at the top of each stalk
DROOP = 0.9                    # how much a stalk's tip drops as it leans

CALM_LEAN = 0.25               # columns the tips lean with no gust
GUST_LEAN = 2.2                # ...and further in a full gust
GUST_WIDTH = 7.0               # columns across one gust
GUST_SPEED = 5.0               # columns/sec the gusts roll across
GUST_CALM_S = 9.0              # roughly how long between stronger and calmer spells
FLUTTER = 0.18                 # columns of small, quick wobble...
FLUTTER_HZ = 0.9
SPRING_HZ = 0.8                # how quickly a stalk springs back...
SPRING_DAMPING = 0.25          # ...and how soon it settles (1 = no overshoot)
SHEEN = 0.6                    # stalks bent over this much brighter

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# DRAWING
# ============================================================

@micropython.viper
def _stalks(light: ptr16, stalks: ptr32, n: int, p: ptr32, colors: ptr16):
    """Add n stalks to light[]. Each has 5 entries in stalks: base x, tip
    lean, height, 65536 / height and brightness (Q8 but the fourth).
    colors holds the stem then head color. Each row of a stalk is a bar
    shared out to the columns it overlaps, so it glides smoothly between
    them."""
    cols = p[0]
    rows = p[1]
    stem_w = p[2]
    head_w = p[3]
    head_len = p[4]
    top = 255 * 16
    i = 0
    while i < n:
        s = i * 5
        x0 = stalks[s + 0]
        lean = stalks[s + 1]
        h = stalks[s + 2]
        inv_h = stalks[s + 3]
        k = stalks[s + 4]
        row = 0
        while row < rows:
            y = row << 8
            if y >= h:
                break
            cover = h - y                    # how much of this row it reaches
            if cover > 256:
                cover = 256
            f = ((y + 128) * inv_h) >> 16    # how far up the stalk, Q8
            x = x0 + ((lean * ((f * f) >> 8)) >> 8)
            # 0 in the stem, 256 in the ear, blending over a row.
            m = y + 128 - (h - head_len)
            if m < 0:
                m = 0
            elif m > 256:
                m = 256
            w = stem_w + (((head_w - stem_w) * m) >> 8)
            sr = int(colors[0])
            sg = int(colors[1])
            sb = int(colors[2])
            r = sr + (((int(colors[3]) - sr) * m) >> 8)
            g = sg + (((int(colors[4]) - sg) * m) >> 8)
            b = sb + (((int(colors[5]) - sb) * m) >> 8)
            amount = (cover * k) >> 8
            left = x - (w >> 1)
            right = left + w
            c = (left + 128) >> 8
            while c < cols:
                cell = c << 8
                if cell - 128 >= right:
                    break
                lo = cell - 128
                if left > lo:
                    lo = left
                hi = cell + 128
                if right < hi:
                    hi = right
                if c >= 0 and hi > lo:
                    a = ((hi - lo) * amount) >> 8
                    o = 3 * (row * cols + c)
                    v = int(light[o + 0]) + ((r * a) >> 8)
                    light[o + 0] = v if v < top else top
                    v = int(light[o + 1]) + ((g * a) >> 8)
                    light[o + 1] = v if v < top else top
                    v = int(light[o + 2]) + ((b * a) >> 8)
                    light[o + 2] = v if v < top else top
                c += 1
            row += 1
        i += 1


# ============================================================
# STALKS
# ============================================================

class Stalk:
    def __init__(self, x, height, shade):
        self.x = x
        self.height = height
        self.shade = shade
        self.lean = CALM_LEAN
        self.speed = 0.0
        self.flutter_at = random.uniform(0, 200)


def _field():
    stalks = []
    step = (COLS - 1) / (STALKS - 1)
    for i in range(BACK_STALKS):
        x = (i + 0.5) * step + random.uniform(-0.25, 0.25)
        stalks.append(Stalk(x, random.uniform(*HEIGHT) * 0.85, BACK_SHADE * random.uniform(0.8, 1.0)))
    for i in range(STALKS):
        x = i * step + random.uniform(-0.3, 0.3)
        stalks.append(Stalk(x, random.uniform(*HEIGHT), random.uniform(0.75, 1.0)))
    return stalks


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def wheat_field(strips):
    canvas = Canvas(strips)
    light = canvas.light
    sky = array.array("H", [0] * (ROWS * COLS * 3))
    for row in range(ROWS):
        r, g, b = to_light(SKY[row])
        for col in range(COLS):
            o = 3 * (row * COLS + col)
            sky[o], sky[o + 1], sky[o + 2] = r, g, b
    colors = array.array("H", to_light(STEM_COLOR) + to_light(HEAD_COLOR))

    field = _field()
    n = len(field)
    params = array.array("i", [0] * (n * 5))
    p = array.array("i", [COLS, ROWS, q8(STEM_WIDTH), q8(HEAD_WIDTH), q8(HEAD_LENGTH)])

    stiffness = (2 * math.pi * SPRING_HZ) ** 2
    damping = 2 * SPRING_DAMPING * math.sqrt(stiffness)
    gx = 1 / GUST_WIDTH
    gust_at = calm_at = 0.0
    last = utime.ticks_ms()

    while True:
        frame_start = utime.ticks_ms()
        dt = min(100, utime.ticks_diff(frame_start, last)) / 1000
        last = frame_start
        # Moving the noise one way moves the gusts the other.
        gust_at = drift(gust_at, -GUST_SPEED / GUST_WIDTH, dt)
        calm_at = drift(calm_at, 1 / GUST_CALM_S, dt)
        # Stronger and calmer spells: 0.25 to 1.
        strength = 0.25 + 0.75 * noise(q8(calm_at), 3000, PERM) / 255

        for i, s in enumerate(field):
            # Gusts: the stronger parts of the noise, eased in.
            g = (noise(q8(s.x * gx + gust_at), 7000, PERM) - 120) / 90
            g = 0.0 if g < 0 else (1.0 if g > 1 else g)
            g = g * g * (3 - 2 * g) * strength
            s.flutter_at = drift(s.flutter_at, FLUTTER_HZ, dt)
            target = CALM_LEAN + GUST_LEAN * g + FLUTTER * (noise(q8(s.flutter_at), 11000, PERM) - 128) / 128
            s.speed += (stiffness * (target - s.lean) - damping * s.speed) * dt
            s.lean += s.speed * dt

            bent = (s.lean - CALM_LEAN) / GUST_LEAN
            bent = 0.0 if bent < 0 else (1.0 if bent > 1 else bent)
            r = s.lean / s.height
            h = s.height * max(0.5, 1 - DROOP * r * r)
            o = 5 * i
            params[o] = q8(s.x)
            params[o + 1] = q8(s.lean)
            params[o + 2] = q8(h)
            params[o + 3] = int(65536 / h)
            params[o + 4] = q8(s.shade * (1 + SHEEN * bent))

        light[:] = sky
        _stalks(light, params, n, p, colors)
        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
