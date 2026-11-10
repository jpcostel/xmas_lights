import array
import math
import random
import utime
from canvas import Canvas, to_light
from faces import Eyes
from grid import ROWS, COLS
from shapes import Ellipse, Polygon, SOFT, ease

# ============================================================
# CONFIGURATION
# ============================================================
# Santa in his sleigh. It starts wide, from the side: Santa sitting in
# his sleigh with Rudolph out in front. As it zooms in on his face he turns his head to
# smile out at you, and the close-up is so close the bottom of his
# beard is cut off, leaving room for big eyes that look around and
# blink. Partway through he says HO HO HO: each HO shows on its own in
# turn, then all three blink together and scroll off to the left, his
# face scrolling back in behind them, laughing. Then he turns back to the road as
# it zooms back out, and the sleigh takes off, flying away up to the
# right, then comes back in from the left for a landing, and round
# again.
#
# Positions are in "close-up" units: at full zoom one unit is one LED,
# x = column and y = row (0 = bottom), so the face's features land on
# the LEDs. The wide view sees the same world from further back.
# Colors are as they'd look with gamma off.

SKIN = (130, 58, 28)
CHEEKS = (210, 30, 30)
NOSE = (210, 25, 15)
# The eyes are flipped from life: dark, with a bright pupil. On the
# LEDs a lit pupil reads as where he's looking; a dark one splitting a
# white eye just looked confusing.
EYE = (0, 0, 0)
PUPIL = (200, 200, 200)
LASH = (20, 5, 0)
MOUTH = (110, 8, 8)
BEARD = (120, 120, 120)
MOUSTACHE = (200, 200, 200)
FUR = (170, 170, 165)
RED = (170, 0, 0)
SLEIGH = (150, 0, 10)
GOLD = (200, 140, 0)
MITTENS = (0, 60, 12)
GROUND = (60, 60, 72)
EVERGREEN = (0, 32, 8)         # dim: they're background
TRUNK = (40, 18, 4)
LAUGH_MOUTH = (45, 0, 0)
REINDEER = (95, 48, 15)
ANTLERS = (150, 110, 60)
RUDOLPH = (255, 0, 0)          # his nose
COAL = (12, 12, 14)

# The close-up, row by row: hat brim 7, eyes 5-6, nose 3-4, moustache 2,
# mouth 1. Eyes: 3 LEDs wide with a pupil one LED wide that looks left,
# ahead or right; three lit LEDs between them keep them apart.
EYES = [(9.0, 5.5), (15.0, 5.5)]
EYE_SIZE = (1.6, 1.05)
PUPIL_SIZE = (0.55, 1.05)
LOOKS = [(0.0, 0.0), (0.0, 0.0), (-1.0, 0.0), (1.0, 0.0)]   # pupil moves a whole LED
# Laughing eyes, squeezed into happy arcs: the LEDs (column, row) of ^ ^.
LAUGH_EYES = [(9, 6), (8, 5), (10, 5), (15, 6), (14, 5), (16, 5)]
CRISP = 0.45                   # edge softness of the small features

# The face's features sit on a rounded head: those with a depth (how
# far out from the head's middle they are) slide round and squeeze as
# he turns his head, and go out of sight round the back.
HEAD_X = 12.0
PROFILE = 80.0                 # degrees his head is turned toward Rudolph
FACE_DEPTH = 6.4
BEARD_DEPTH = 3.0
NOSE_DEPTH = 7.4

# (kind, color, where[, depth]), drawn in this order, back to front:
# ellipses ("ellipse", or "crisp" for small features) are
# (x, y, rx, ry[, alpha]), polygons ("poly") their corners.
WORLD = [
    ("poly", GROUND, [(-70, -14.8), (110, -14.8), (110, -40), (-70, -40)]),
    # Two evergreens behind it all, clear of the close-up of his face.
] + [
    part
    for tx in (-10.0, 64.0)
    for part in (
        ("poly", TRUNK, [(tx - 1.2, -14.8), (tx + 1.2, -14.8), (tx + 1.2, -12.0), (tx - 1.2, -12.0)]),
        ("poly", EVERGREEN, [(tx - 8.0, -12.5), (tx + 8.0, -12.5), (tx, -1.5)]),
        ("poly", EVERGREEN, [(tx - 6.5, -6.5), (tx + 6.5, -6.5), (tx, 4.0)]),
        ("poly", EVERGREEN, [(tx - 5.0, -0.5), (tx + 5.0, -0.5), (tx, 9.5)]),
    )
] + [
    # Rudolph, out in front: legs, tail, body, neck, head, antlers, eye
    # and that nose.
    ("poly", REINDEER, [(37.4, -8.5), (38.6, -8.5), (38.6, -14.4), (37.4, -14.4)]),
    ("poly", REINDEER, [(40.4, -8.5), (41.6, -8.5), (41.6, -14.4), (40.4, -14.4)]),
    ("poly", REINDEER, [(47.4, -8.5), (48.6, -8.5), (48.6, -14.4), (47.4, -14.4)]),
    ("poly", REINDEER, [(50.4, -8.5), (51.6, -8.5), (51.6, -14.4), (50.4, -14.4)]),
    ("ellipse", FUR, (36.4, -4.5, 1.1, 1.1)),
    ("ellipse", REINDEER, (44.0, -6.0, 7.6, 3.4)),
    ("poly", REINDEER, [(48.5, -4.3), (51.8, -5.3), (54.2, -0.1), (51.0, 1.1)]),
    ("poly", ANTLERS, [(51.0, 2.5), (52.6, 2.5), (50.6, 7.3), (49.0, 7.3)]),
    ("poly", ANTLERS, [(53.0, 2.5), (54.6, 2.5), (56.0, 7.3), (54.4, 7.3)]),
    ("ellipse", REINDEER, (53.4, 1.1, 3.0, 1.9)),
    ("ellipse", COAL, (53.8, 1.7, 0.45, 0.45)),
    ("ellipse", RUDOLPH, (56.6, 0.6, 1.1, 1.1)),
    # Santa, from the side: hat...
    ("poly", RED, [(16.0, 12.2), (19.0, 10.2), (25.0, 9.0)]),
    ("ellipse", FUR, (26.0, 8.8, 1.7, 1.7)),
    ("poly", RED, [(5.6, 7.4), (18.4, 7.4), (17.5, 11.6), (10.0, 13.0)]),
    # ...his body, and his arm reaching out to the front of the sleigh...
    ("ellipse", RED, (11.0, -3.5, 6.8, 6.0)),
    ("poly", FUR, [(16.6, -0.5), (18.0, -1.5), (18.0, -8.0), (16.6, -8.0)]),
    ("ellipse", RED, (18.5, -4.0, 5.0, 2.3)),
    ("ellipse", MITTENS, (23.0, -4.5, 1.9, 1.9)),
    # ...the sleigh in front of him, on gold runners...
    ("poly", SLEIGH, [(-9.0, 0.5), (-3.0, -0.5), (-3.0, -11.6), (-6.5, -11.6)]),
    ("poly", SLEIGH, [(-6.0, -6.5), (27.0, -6.5), (29.0, -11.6), (-4.5, -11.6)]),
    ("ellipse", SLEIGH, (29.5, -6.5, 3.0, 2.8)),
    ("poly", GOLD, [(-4.0, -13.4), (28.0, -13.4), (28.0, -14.4), (-4.0, -14.4)]),
    ("ellipse", GOLD, (29.5, -12.6, 1.9, 1.9)),
    # ...and his head: beard behind the face, then the face's features.
    ("ellipse", BEARD, (12.0, 1.0, 9.2, 6.4), BEARD_DEPTH),
    ("ellipse", SKIN, (12.0, 4.6, 6.4, 2.7)),
    ("ellipse", CHEEKS, (7.4, 3.6, 1.5, 0.9, 0.55), FACE_DEPTH),
    ("ellipse", CHEEKS, (16.6, 3.6, 1.5, 0.9, 0.55), FACE_DEPTH),
    ("crisp", EYE, EYES[0] + EYE_SIZE, FACE_DEPTH),
    ("crisp", EYE, EYES[1] + EYE_SIZE, FACE_DEPTH),
    ("crisp", MOUTH, (12.0, 1.0, 2.4, 0.55), FACE_DEPTH),
    ("ellipse", MOUSTACHE, (9.5, 2.3, 3.1, 0.85), FACE_DEPTH),
    ("ellipse", MOUSTACHE, (14.5, 2.3, 3.1, 0.85), FACE_DEPTH),
    ("crisp", NOSE, (12.0, 3.9, 1.5, 1.1), NOSE_DEPTH),
    # The hat's soft fur trim: one row across his head, close up.
    ("ellipse", FUR, (12.0, 7.1, 6.8, 0.5)),
]

# The two views: zoom (LEDs per unit) and the world point at the middle
# of the mantle.
WIDE = (0.28, 24.5, -0.9)
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
WIDE_S = (2.0, 3.5)            # the whole scene
ZOOM_S = 3.5                   # zooming in or out...
TURN_START_S = 2.0             # ...his head starting to turn this far into it, once
TURN_S = 1.45                  # his face is big enough to see it (the reverse going out)
LAUGH_S = 2.5                  # laughing, once his face is back after HO HO HO...
LAUGH_HZ = 2.5                 # ...mouth opening wide with each ha
TAKEOFF_S = 3.5                # a run along the snow, then up and away to the right...
LAND_S = 4.0                   # ...and back in from the left
FLY_X = 100.0                  # how far it flies off to the side...
FLY_Y = 35.0                   # ...and up
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

    def __init__(self, kind, color, where, depth=None):
        self.kind = kind
        self.where = where
        self.depth = depth
        # The ground and trees stay put when the sleigh flies.
        self.flies = color not in (GROUND, EVERGREEN, TRUNK)
        if kind == "poly":
            self.shape = Polygon(color, sides=len(where))
        else:
            self.shape = Ellipse(color, soft=CRISP if kind == "crisp" else SOFT)

    def place(self, zoom, cx, cy, turn=0.0, fly_x=0.0, fly_y=0.0):
        """Set the shape for a camera, with his head turned turn degrees
        toward Rudolph and the sleigh flown (fly_x, fly_y) from where it
        stands; it's hidden if it's off the mantle."""
        if self.flies:
            cx -= fly_x
            cy -= fly_y
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
        if self.depth:
            x, rx, seen = turned(x, rx, self.depth, turn)
            alpha *= seen
        x = (x - cx) * zoom + 12.0
        y = (y - cy) * zoom + 3.5
        rx *= zoom
        ry *= zoom
        if alpha > 0 and x + rx > -1 and x - rx < COLS and y + ry > -1 and y - ry < ROWS:
            self.shape.set(x, y, rx, ry, alpha)
        else:
            self.shape.shown = False

    def draw(self, light):
        self.shape.draw(light)


def turned(x, rx, depth, turn):
    """Where a feature of the face at x (rx across) ends up with his head
    turned turn degrees, and how much of it can be seen (0..1)."""
    if not turn:
        return x, rx, 1.0
    a = math.asin(max(-1.0, min(1.0, (x - HEAD_X) / depth))) + math.radians(turn)
    facing = math.cos(a)
    # Squeezed as it turns away, gone once it's round the back.
    return (HEAD_X + depth * math.sin(a), rx * max(0.4, facing),
            min(1.0, max(0.0, (facing + 0.15) / 0.3)))


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
    parts = [Part(*part) for part in WORLD]
    pupils = [Ellipse(PUPIL, soft=CRISP) for _ in EYES]
    lids = [Ellipse(SKIN, soft=CRISP) for _ in EYES]
    lashes = [Ellipse(LASH, soft=CRISP) for _ in EYES]
    laugh_cheeks = [Ellipse(CHEEKS, x, 3.6, 1.6, 1.0, 0.6) for x in (7.4, 16.6)]
    laugh_mouth = Ellipse(LAUGH_MOUTH, soft=CRISP)

    backdrop = None              # the ground and trees in the wide view

    def paint(f, turn=0.0, with_pupils=True, fly_x=0.0, fly_y=0.0):
        zoom, cx, cy = _view(f)
        # In the wide view only the sleigh moves: the rest is painted once.
        if f == 0.0 and backdrop:
            light[:] = backdrop
            moving = [part for part in parts if part.flies]
        else:
            canvas.clear()
            moving = parts
        for part in moving:
            part.place(zoom, cx, cy, turn, fly_x, fly_y)
            part.draw(light)
        if with_pupils:
            for pupil, (x, y) in zip(pupils, EYES):
                x, rx, seen = turned(x, PUPIL_SIZE[0], FACE_DEPTH, turn)
                pupil.set((x + fly_x - cx) * zoom + 12.0, (y + fly_y - cy) * zoom + 3.5,
                          rx * zoom, PUPIL_SIZE[1] * zoom, seen)
                pupil.draw(light)

    # The still views, painted once.
    canvas.clear()
    for part in parts:
        if not part.flies:
            part.place(*_view(0.0))
            part.draw(light)
    backdrop = array.array("H", light)
    paint(0.0, PROFILE)
    wide = array.array("H", light)
    paint(1.0)
    face_open = array.array("H", light)
    paint(1.0, 0.0, with_pupils=False)
    face = array.array("H", light)

    ho = HoHoHo()
    eyes = Eyes(0.0, BLINK_EVERY_S, BLINK_S, 0.0, LOOKS)
    scene_start = utime.ticks_ms()
    # The cycle: land, wide, zoom in, close up, HO HO HO, close up, zoom
    # out, take off.
    phases = ("land", "wide", "in", "close", "ho", "laugh", "close", "out", "takeoff")
    phase = 0
    start = 0.0
    hold = LAND_S

    while True:
        frame_start = utime.ticks_ms()
        t = utime.ticks_diff(frame_start, scene_start) / 1000
        if t - start >= hold:
            phase = (phase + 1) % len(phases)
            start = t
            what = phases[phase]
            if what == "wide":
                hold = random.uniform(*WIDE_S)
            elif what == "land":
                hold = LAND_S
            elif what == "takeoff":
                hold = TAKEOFF_S
            elif what == "laugh":
                hold = LAUGH_S
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
        elif what == "in":
            # He turns to face us partway into the zoom...
            paint(ease(age / ZOOM_S), PROFILE * (1.0 - ease((age - TURN_START_S) / TURN_S)))
        elif what == "out":
            # ...and back toward Rudolph early in the zoom out.
            paint(1.0 - ease(age / ZOOM_S),
                  PROFILE * ease((age - (ZOOM_S - TURN_START_S - TURN_S)) / TURN_S))
        elif what == "takeoff":
            # A run along the snow, then climbing away, faster and faster.
            u = age / TAKEOFF_S
            lift = max(0.0, (u - 0.25) / 0.75)
            paint(0.0, PROFILE, True, FLY_X * u * u, FLY_Y * lift * lift)
        elif what == "land":
            # Gliding in from high on the left, slowing, touching down just
            # before it comes to a stop.
            u = 1.0 - min(1.0, age / LAND_S)
            paint(0.0, PROFILE, True, -FLY_X * u * u, FLY_Y * u * u * u)
        elif what == "ho":
            ho.draw(light, age, face_open)
        elif what == "laugh":
            # Eyes squeezed into happy arcs, rosy cheeks, and a big open
            # mouth with each ha.
            light[:] = face
            for lid, (x, y) in zip(lids, EYES):
                lid.set(x, y, EYE_SIZE[0], EYE_SIZE[1])
                lid.draw(light)
            for col, row in LAUGH_EYES:
                o = 3 * (row * COLS + col)
                light[o] = light[o + 1] = light[o + 2] = 0
            for cheek in laugh_cheeks:
                cheek.draw(light)
            ha = abs(math.sin(math.pi * LAUGH_HZ * age))
            laugh_mouth.set(12.0, 0.8, 2.7, 0.75 + 0.4 * ha)
            laugh_mouth.draw(light)
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
                    lids[i].set(x, y, EYE_SIZE[0], EYE_SIZE[1], shut)
                    lids[i].draw(light)
                    lashes[i].set(x, y - 0.5, EYE_SIZE[0] * 0.9, 0.45, shut)
                    lashes[i].draw(light)
        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
