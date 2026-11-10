import array
import random
import utime
from canvas import Canvas, to_light
from faces import Eyes
from grid import ROWS, COLS
from shapes import Ellipse, Polygon, SOFT, ease

# ============================================================
# CONFIGURATION
# ============================================================
# Santa at the North Pole. It starts wide: Santa head to boots, a
# striped North Pole on one side and a snowman on the other. Then it
# zooms in on his face, so close the bottom of his beard is cut off,
# leaving room for big eyes that look around and blink. Partway
# through he says HO HO HO: each HO shows on its own in turn, then all
# three blink together and scroll off to the left, his face scrolling
# back in behind them. Then it zooms back out, and round again.
#
# Positions are in "close-up" units: at full zoom one unit is one LED,
# x = column and y = row (0 = bottom), so the face's features land on
# the LEDs. The wide view sees the same world from further back.
# Colors are as they'd look with gamma off.

SKIN = (130, 58, 28)
CHEEKS = (210, 30, 30)
NOSE = (210, 25, 15)
EYE_WHITE = (190, 190, 190)
PUPIL = (0, 0, 0)
LASH = (20, 5, 0)
MOUTH = (110, 8, 8)
BEARD = (120, 120, 120)
MOUSTACHE = (200, 200, 200)
FUR = (170, 170, 165)
RED = (170, 0, 0)
BELT = (14, 10, 6)
BUCKLE = (200, 140, 0)
MITTENS = (0, 60, 12)
BOOTS = (22, 12, 6)
SNOW = (150, 150, 160)
GROUND = (60, 60, 72)
COAL = (12, 12, 14)
CARROT = (220, 70, 0)
SCARF = (0, 110, 20)
POLE = (170, 170, 165)
STRIPE = (190, 0, 0)
GOLD = (220, 160, 0)

# The close-up, row by row: hat brim 7, eyes 5-6, nose 3-4, moustache 2,
# mouth 1. Eyes: whites 3 LEDs wide with a pupil one LED wide that looks
# left, ahead or right; three lit LEDs between them keep them apart.
EYES = [(9.0, 5.5), (15.0, 5.5)]
WHITE_SIZE = (1.6, 1.05)
PUPIL_SIZE = (0.55, 1.05)
LOOKS = [(0.0, 0.0), (0.0, 0.0), (-1.0, 0.0), (1.0, 0.0)]   # pupil moves a whole LED
CRISP = 0.45                   # edge softness of the small features

# (kind, color, where), drawn in this order, back to front: ellipses
# ("ellipse", or "crisp" for small features) are (x, y, rx, ry[, alpha]),
# polygons ("poly") their corners.
WORLD = [
    ("poly", GROUND, [(-70, -16.6), (94, -16.6), (94, -40), (-70, -40)]),
    # The North Pole: a striped pole with a gold ball on top.
    ("poly", POLE, [(-21.3, -16.6), (-18.7, -16.6), (-18.7, 9.0), (-21.3, 9.0)]),
] + [
    ("poly", STRIPE, [(-21.3, y), (-18.7, y + 1.6), (-18.7, y + 3.2), (-21.3, y + 1.6)])
    for y in range(-16, 8, 4)
] + [
    ("ellipse", GOLD, (-20.0, 10.6, 2.3, 2.3)),
    # A snowman, with a top hat, coal eyes and buttons, a carrot nose and
    # a scarf.
    ("ellipse", SNOW, (44.0, -11.0, 5.6, 5.6)),
    ("ellipse", SNOW, (44.0, -3.0, 4.3, 4.3)),
    ("ellipse", SNOW, (44.0, 3.6, 3.3, 3.3)),
    ("ellipse", SCARF, (44.0, 0.6, 3.8, 0.9)),
    ("ellipse", COAL, (44.0, -2.5, 0.7, 0.7)),
    ("ellipse", COAL, (44.0, -5.0, 0.7, 0.7)),
    ("ellipse", COAL, (42.9, 4.5, 0.6, 0.6)),
    ("ellipse", COAL, (45.1, 4.5, 0.6, 0.6)),
    ("poly", CARROT, [(43.5, 3.7), (43.5, 2.7), (48.0, 3.0)]),
    ("ellipse", COAL, (44.0, 6.6, 4.2, 0.7)),
    ("poly", COAL, [(41.6, 6.6), (46.4, 6.6), (46.4, 11.0), (41.6, 11.0)]),
    # Santa: hat...
    ("poly", RED, [(16.0, 12.2), (19.0, 10.2), (25.0, 9.0)]),
    ("ellipse", FUR, (26.0, 8.8, 1.7, 1.7)),
    ("poly", RED, [(3.0, 7.4), (21.0, 7.4), (19.0, 11.6), (10.0, 13.0)]),
    # ...body: arms, coat with its white trim, belt and buckle, mittens, boots...
    ("ellipse", RED, (1.5, -6.5, 2.6, 5.2)),
    ("ellipse", RED, (22.5, -6.5, 2.6, 5.2)),
    ("poly", RED, [(3.0, -2.0), (21.0, -2.0), (24.0, -13.5), (0.0, -13.5)]),
    ("poly", FUR, [(10.8, -2.0), (13.2, -2.0), (13.2, -13.5), (10.8, -13.5)]),
    ("poly", FUR, [(0.0, -12.3), (24.0, -12.3), (24.0, -14.0), (0.0, -14.0)]),
    ("poly", BELT, [(1.0, -8.3), (23.0, -8.3), (23.3, -10.5), (0.7, -10.5)]),
    ("ellipse", BUCKLE, (12.0, -9.4, 1.6, 1.3)),
    ("ellipse", MITTENS, (1.0, -11.8, 1.9, 1.9)),
    ("ellipse", MITTENS, (23.0, -11.8, 1.9, 1.9)),
    ("ellipse", BOOTS, (7.0, -15.0, 4.2, 1.8)),
    ("ellipse", BOOTS, (17.0, -15.0, 4.2, 1.8)),
    # ...and head: beard behind the face, then the face's features.
    ("ellipse", BEARD, (12.0, 1.0, 9.2, 6.4)),
    ("ellipse", SKIN, (12.0, 4.6, 6.4, 2.7)),
    ("ellipse", CHEEKS, (7.4, 3.6, 1.5, 0.9, 0.55)),
    ("ellipse", CHEEKS, (16.6, 3.6, 1.5, 0.9, 0.55)),
    ("crisp", EYE_WHITE, EYES[0] + WHITE_SIZE),
    ("crisp", EYE_WHITE, EYES[1] + WHITE_SIZE),
    ("crisp", MOUTH, (12.0, 1.0, 2.4, 0.55)),
    ("ellipse", MOUSTACHE, (9.5, 2.3, 3.1, 0.85)),
    ("ellipse", MOUSTACHE, (14.5, 2.3, 3.1, 0.85)),
    ("crisp", NOSE, (12.0, 3.9, 1.5, 1.1)),
    ("ellipse", FUR, (12.0, 7.15, 9.6, 0.7)),
]

# The two views: zoom (LEDs per unit) and the world point at the middle
# of the mantle.
WIDE = (0.26, 12.0, -2.0)
CLOSE = (1.0, 12.0, 3.5)

# HO HO HO, in 3x5 letters (taller ones read as thin bars): each HO is
# 7 columns, two apart, filling the 25 columns. Each glyph is its rows,
# top first.
GLYPHS = {
    "H": ("X.X", "X.X", "XXX", "X.X", "X.X"),
    "O": ("XXX", "X.X", "X.X", "X.X", "XXX"),
}
# Each HO: left column, top row (stepping down from the top left), color.
HOS = [(0, 7, (200, 0, 0)), (9, 6, (170, 170, 170)), (18, 5, (200, 0, 0))]
HO_S = 1.0                     # each HO on its own...
FLASH_ON_S = 0.6               # ...then all three blink together...
FLASH_OFF_S = 0.4
FLASHES = 3
SCROLL_GAP = 3                 # ...and scroll off, the face this far behind...
SCROLL_SPEED = 14.0            # ...at this many columns/sec

# Timing, in seconds.
WIDE_S = (6.0, 10.0)           # the whole scene
ZOOM_S = 3.5                   # zooming in or out
BEFORE_HO_S = (8.0, 14.0)      # close up, then HO HO HO...
AFTER_HO_S = (6.0, 12.0)       # ...then a while longer before zooming out
BLINK_EVERY_S = (3.0, 7.0)
BLINK_S = 0.3

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# THE WORLD, THROUGH A CAMERA
# ============================================================

class Part:
    """One shape of the world, placed on the mantle for a view."""

    def __init__(self, kind, color, where):
        self.kind = kind
        self.where = where
        if kind == "poly":
            self.shape = Polygon(color, sides=len(where))
        else:
            self.shape = Ellipse(color, soft=CRISP if kind == "crisp" else SOFT)

    def place(self, zoom, cx, cy):
        """Set the shape for a camera; it's hidden if it's off the mantle."""
        if self.kind == "poly":
            pts = [((x - cx) * zoom + 12.0, (y - cy) * zoom + 3.5) for x, y in self.where]
            on = (max(x for x, _ in pts) > -1 and min(x for x, _ in pts) < COLS
                  and max(y for _, y in pts) > -1 and min(y for _, y in pts) < ROWS)
            if on:
                self.shape.set(pts)
            self.shape.shown = on
            return
        x, y, rx, ry = self.where[:4]
        alpha = self.where[4] if len(self.where) > 4 else 1.0
        x = (x - cx) * zoom + 12.0
        y = (y - cy) * zoom + 3.5
        rx *= zoom
        ry *= zoom
        if x + rx > -1 and x - rx < COLS and y + ry > -1 and y - ry < ROWS:
            self.shape.set(x, y, rx, ry, alpha)
        else:
            self.shape.shown = False

    def draw(self, light):
        self.shape.draw(light)


def _view(f):
    """The camera f of the way from the wide view to the close-up:
    zooming steadily (in proportion), the middle moving evenly with how
    much of the world is in view."""
    z0, x0, y0 = WIDE
    z1, x1, y1 = CLOSE
    zoom = z0 * (z1 / z0) ** f
    g = (1 / z0 - 1 / zoom) / (1 / z0 - 1 / z1)
    return zoom, x0 + (x1 - x0) * g, y0 + (y1 - y0) * g


# ============================================================
# HO HO HO
# ============================================================

def _word(left, top, color):
    """A light buffer with one HO in it, its top left corner at column
    left, row top."""
    out = array.array("H", [0] * (ROWS * COLS * 3))
    c = to_light(color)
    x = left
    for letter in "HO":
        for i, line in enumerate(GLYPHS[letter]):
            row = top - i
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
    def __init__(self):
        self.words = [_word(x, top, color) for x, top, color in HOS]
        self.all = array.array("H", self.words[0])
        for w in self.words[1:]:
            for i in range(len(w)):
                self.all[i] += w[i]
        self.dark = array.array("H", [0] * len(self.all))
        self.flashes_end = len(HOS) * HO_S + FLASHES * (FLASH_ON_S + FLASH_OFF_S) + FLASH_ON_S
        self.length = self.flashes_end + (COLS + SCROLL_GAP) / SCROLL_SPEED

    def draw(self, light, age, face):
        """Draw the sequence age seconds in; face scrolls in behind."""
        if age < len(HOS) * HO_S:
            light[:] = self.words[int(age / HO_S)]
        elif age < self.flashes_end:
            b = (age - len(HOS) * HO_S) % (FLASH_ON_S + FLASH_OFF_S)
            light[:] = self.all if b < FLASH_ON_S else self.dark
        else:
            shift = min(COLS + SCROLL_GAP, int((age - self.flashes_end) * SCROLL_SPEED))
            light[:] = self.dark
            _place(light, self.all, -shift)
            _place(light, face, COLS + SCROLL_GAP - shift)


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def santa(strips):
    canvas = Canvas(strips)
    light = canvas.light
    parts = [Part(kind, color, where) for kind, color, where in WORLD]
    pupils = [Ellipse(PUPIL, soft=CRISP) for _ in EYES]
    lids = [Ellipse(SKIN, soft=CRISP) for _ in EYES]
    lashes = [Ellipse(LASH, soft=CRISP) for _ in EYES]

    def paint(f, with_pupils=True):
        zoom, cx, cy = _view(f)
        canvas.clear()
        for part in parts:
            part.place(zoom, cx, cy)
            part.draw(light)
        if with_pupils:
            for pupil, (x, y) in zip(pupils, EYES):
                pupil.set((x - cx) * zoom + 12.0, (y - cy) * zoom + 3.5,
                          PUPIL_SIZE[0] * zoom, PUPIL_SIZE[1] * zoom)
                pupil.draw(light)

    # The still views, painted once.
    paint(0.0)
    wide = array.array("H", light)
    paint(1.0)
    face_open = array.array("H", light)
    paint(1.0, with_pupils=False)
    face = array.array("H", light)

    ho = HoHoHo()
    eyes = Eyes(0.0, BLINK_EVERY_S, BLINK_S, 0.0, LOOKS)
    scene_start = utime.ticks_ms()
    # The cycle: wide, zoom in, close up, HO HO HO, close up, zoom out.
    phases = ("wide", "in", "close", "ho", "close", "out")
    phase = 0
    start = 0.0
    hold = random.uniform(*WIDE_S)

    while True:
        frame_start = utime.ticks_ms()
        t = utime.ticks_diff(frame_start, scene_start) / 1000
        if t - start >= hold:
            phase = (phase + 1) % len(phases)
            start = t
            what = phases[phase]
            if what == "wide":
                hold = random.uniform(*WIDE_S)
            elif what in ("in", "out"):
                hold = ZOOM_S
            elif what == "ho":
                hold = ho.length
            else:
                hold = random.uniform(*(BEFORE_HO_S if phases[phase + 1] == "ho" else AFTER_HO_S))
        what = phases[phase]
        age = t - start

        if what == "wide":
            light[:] = wide
        elif what in ("in", "out"):
            f = ease(age / ZOOM_S)
            paint(f if what == "in" else 1.0 - f)
        elif what == "ho":
            ho.draw(light, age, face_open)
        else:
            opened, look_x, _ = eyes.update(t)
            light[:] = face
            shut = 1.0 - opened
            for i, (x, y) in enumerate(EYES):
                pupils[i].set(x + look_x, y, PUPIL_SIZE[0], PUPIL_SIZE[1])
                pupils[i].draw(light)
                # Blinking: skin comes down over the eye, leaving a dark
                # line of lashes along the bottom.
                if shut > 0.02:
                    lids[i].set(x, y, WHITE_SIZE[0], WHITE_SIZE[1], shut)
                    lids[i].draw(light)
                    lashes[i].set(x, y - 0.5, WHITE_SIZE[0] * 0.9, 0.45, shut)
                    lashes[i].draw(light)
        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
