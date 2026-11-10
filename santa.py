import array
import math
import random
import utime
from canvas import Canvas, to_light
from faces import Eyes
from grid import ROWS, COLS
from shapes import Ellipse, Polygon

# ============================================================
# CONFIGURATION
# ============================================================
# Santa, face on: red hat with a white brim and pom-pom, white beard and
# moustache, red nose and rosy cheeks. His eyes blink, look from side
# to side and now and then wink. Every so often he says HO HO HO: each
# HO shows on its own in turn, then all three blink together and
# scroll off to the left, his face scrolling back in behind them.
#
# Positions are in LED spacings: x = column, y = row (0 = bottom).
# Colors are as they'd look with gamma off. At 8 rows each feature
# gets its own rows, lined up on the LEDs: hat 6-7, brim 5, eyes 4,
# nose and cheeks 3, moustache 2, beard 0-1.

SKIN = (130, 58, 28)
NOSE = (210, 25, 15)
CHEEKS = (210, 30, 30)
CHEEK_ALPHA = 0.45
EYE = (0, 0, 0)
BEARD = (120, 120, 120)
MOUSTACHE = (200, 200, 200)
MOUTH = (25, 0, 0)
HAT = (170, 0, 0)
FUR = (170, 170, 165)

BEARD_AT = (12.0, 2.3, 5.2, 3.1)          # x, y, half-width, half-height
FACE = (12.0, 3.7, 3.4, 1.35)
EYES = [(10.5, 4.0), (13.5, 4.0)]         # two LEDs each
EYE_SIZE = (1.05, 0.55)
LOOK_REACH = (1.0, 0.0)                   # a whole LED, so the move is clear...
LOOKS = [(0.0, 0.0), (0.0, 0.0), (-1.0, 0.0), (1.0, 0.0)]   # ...ending on the LEDs
NOSE_AT = (12.0, 3.0, 0.6)
CHEEK_AT = [(9.6, 3.0), (14.4, 3.0)]
CHEEK_R = 0.8
MOUSTACHE_AT = [(10.4, 2.1, 1.9, 0.6), (13.6, 2.1, 1.9, 0.6)]
MOUTH_AT = (12.0, 1.0, 0.9)               # x, y, half-width
HAT_BODY = [(7.0, 5.6), (17.0, 5.6), (17.8, 7.3), (11.0, 8.0)]
HAT_TIP = [(15.6, 7.8), (18.0, 6.4), (21.3, 6.3)]
BRIM_AT = (12.0, 5.05, 5.4, 0.55)
POM_AT = (21.6, 6.5, 0.9)
CRISP = 0.45                              # edge softness of the small features

# Timing, in seconds. One-row eyes blink better slow and seldom: quick
# ones look like a flicker.
BLINK_EVERY_S = (3.0, 7.0)
BLINK_S = 0.28
WINK_EVERY_S = (8.0, 20.0)
WINK_S = 0.6

# HO HO HO, in 3x5 letters (taller ones read as thin bars): each HO is
# 7 columns, two apart, filling the 25 columns. Each glyph is its rows,
# top first.
GLYPHS = {
    "H": ("X.X", "X.X", "XXX", "X.X", "X.X"),
    "O": ("XXX", "X.X", "X.X", "X.X", "XXX"),
}
HOS = [(0, (200, 0, 0)), (9, (170, 170, 170)), (18, (200, 0, 0))]   # left column, color
TEXT_TOP = 6                   # the letters' top row
HO_EVERY_S = (20.0, 45.0)
HO_S = 0.6                     # each HO on its own...
FLASH_ON_S = 0.35              # ...then all three blink together...
FLASH_OFF_S = 0.25
FLASHES = 3
SCROLL_GAP = 3                 # ...and scroll off, the face this far behind...
SCROLL_SPEED = 14.0            # ...at this many columns/sec

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# HO HO HO
# ============================================================

def _word(left, color):
    """A light buffer with one HO in it, its left edge at column left."""
    out = array.array("H", [0] * (ROWS * COLS * 3))
    c = to_light(color)
    x = left
    for letter in "HO":
        for i, line in enumerate(GLYPHS[letter]):
            row = TEXT_TOP - i
            for j, bit in enumerate(line):
                if bit == "X":
                    o = 3 * (row * COLS + x + j)
                    out[o], out[o + 1], out[o + 2] = c
        x += 4
    return out


def _place(dst, src, dx):
    """Copy src into dst moved dx columns right (left if negative); what
    moves off the edge is dropped."""
    lo = max(0, -dx)
    hi = min(COLS, COLS - dx)
    if lo >= hi:
        return
    for row in range(ROWS):
        o = row * COLS * 3
        dst[o + (lo + dx) * 3:o + (hi + dx) * 3] = src[o + lo * 3:o + hi * 3]


class HoHoHo:
    """When it's time, what the screen shows instead of Santa's face."""

    def __init__(self, t):
        self.words = [_word(x, color) for x, color in HOS]
        self.all = array.array("H", self.words[0])
        for w in self.words[1:]:
            for i in range(len(w)):
                self.all[i] += w[i]
        self.dark = array.array("H", [0] * len(self.all))
        self.flashes_end = len(HOS) * HO_S + FLASHES * (FLASH_ON_S + FLASH_OFF_S) + FLASH_ON_S
        self.start = t + random.uniform(*HO_EVERY_S)

    def draw(self, light, t, face):
        """Draw this frame into light and return True, or return False
        when it's the face's turn."""
        age = t - self.start
        if age < 0:
            return False
        if age < len(HOS) * HO_S:
            light[:] = self.words[int(age / HO_S)]
            return True
        if age < self.flashes_end:
            b = (age - len(HOS) * HO_S) % (FLASH_ON_S + FLASH_OFF_S)
            light[:] = self.all if b < FLASH_ON_S else self.dark
            return True
        shift = int((age - self.flashes_end) * SCROLL_SPEED)
        if shift >= COLS + SCROLL_GAP:
            self.start = t + random.uniform(*HO_EVERY_S)
            return False
        light[:] = self.dark
        _place(light, self.all, -shift)
        _place(light, face, COLS + SCROLL_GAP - shift)
        return True


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def santa(strips):
    canvas = Canvas(strips)
    light = canvas.light

    # Everything but the eyes stays still: paint it once and copy it in
    # each frame.
    still = [Polygon(HAT, HAT_BODY), Polygon(HAT, HAT_TIP, sides=3),
             Ellipse(BEARD, *BEARD_AT), Ellipse(SKIN, *FACE)]
    still += [Ellipse(CHEEKS, x, y, CHEEK_R, CHEEK_R * 0.7, CHEEK_ALPHA) for x, y in CHEEK_AT]
    still.append(Ellipse(NOSE, NOSE_AT[0], NOSE_AT[1], NOSE_AT[2], NOSE_AT[2] * 0.8, soft=CRISP))
    mx, my, mw = MOUTH_AT
    still.append(Ellipse(MOUTH, mx, my, mw, 0.3, 0.5, soft=CRISP))
    still += [Ellipse(MOUSTACHE, *m, soft=CRISP) for m in MOUSTACHE_AT]
    still.append(Ellipse(FUR, *BRIM_AT))
    still.append(Ellipse(FUR, POM_AT[0], POM_AT[1], POM_AT[2], POM_AT[2]))
    for shape in still:
        shape.draw(light)
    face = array.array("H", light)

    eye_shapes = [Ellipse(EYE, soft=CRISP) for _ in EYES]
    # The face as it scrolls back in: eyes open, looking ahead.
    for shape, (ex, ey) in zip(eye_shapes, EYES):
        shape.set(ex, ey, EYE_SIZE[0], EYE_SIZE[1])
        shape.draw(light)
    face_open = array.array("H", light)
    ho = HoHoHo(0.0)
    scene_start = utime.ticks_ms()
    eyes = Eyes(0.0, BLINK_EVERY_S, BLINK_S, 0.0, LOOKS)
    wink_at = random.uniform(*WINK_EVERY_S)

    while True:
        frame_start = utime.ticks_ms()
        t = utime.ticks_diff(frame_start, scene_start) / 1000

        opened, look_x, look_y = eyes.update(t)
        g = t - wink_at
        wink = 0.0
        if g >= WINK_S:
            wink_at = t + random.uniform(*WINK_EVERY_S)
        elif g >= 0.0:
            wink = math.sin(math.pi * g / WINK_S)

        if not ho.draw(light, t, face_open):
            light[:] = face
            x = LOOK_REACH[0] * look_x
            for i, (ex, ey) in enumerate(EYES):
                shut = opened if i == 0 else min(opened, 1.0 - wink)
                eye_shapes[i].set(ex + x, ey, EYE_SIZE[0], EYE_SIZE[1] * max(0.25, shut), 0.6 + 0.4 * shut)
                eye_shapes[i].draw(light)
        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
