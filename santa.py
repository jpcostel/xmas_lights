import array
import math
import random
import utime
from canvas import Canvas, to_light
from grid import ROWS, COLS
from shapes import Ellipse, Polygon, SOFT, ease

# ============================================================
# CONFIGURATION
# ============================================================
# Santa in his sleigh. It starts wide, from the side: Santa sitting low
# in his sleigh, his hat flopped over with its pom-pom, Rudolph out in
# front and evergreens behind. As it zooms in on his face he turns his
# head to smile out at you, and the close-up is so close the bottom of
# his beard is cut off, leaving room for big eyes. He looks left, then
# right, then back at you, and says HO HO HO: each HO shows on its own
# in turn, then all three blink together and scroll off to the left,
# his face scrolling back in behind them, laughing. Then he turns back
# to the road as it zooms back out, and the sleigh takes off, flying
# away up to the right, then comes back in from the left for a landing,
# and round again. Light snow falls in the wide view, some behind
# everything, some between the trees and the sleigh, some in front of it
# all. Zooming in, it spreads out past you, and it's gone as soon as he
# turns his head; it comes back once he's turned back to the road.
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
MOUTH = (80, 6, 6)
BEARD = (120, 120, 120)
MOUSTACHE = (200, 200, 200)
FUR = (170, 170, 165)
RED = (170, 0, 0)
SLEIGH = (150, 0, 10)
GOLD = (200, 140, 0)
MITTENS = (0, 60, 12)
GROUND = (60, 60, 72)
EVERGREEN = (0, 32, 8)         # dim: they're background...
FAR_EVERGREEN = (0, 20, 5)     # ...this one dimmer still: further back
SNOWFLAKE = (255, 255, 255)    # mixed in faintly: see SNOW_ALPHA
TRUNK = (40, 18, 4)
REINDEER = (95, 48, 15)
ANTLERS = (150, 110, 60)
RUDOLPH = (255, 0, 0)          # his nose
COAL = (12, 12, 14)

# The close-up, row by row: hat 7, its fur trim 6, eyes 4-5, nose and
# cheeks 3, moustache 2, mouth 0-1. Eyes: 3 LEDs wide with a pupil one
# LED wide that looks left, ahead or right; three lit LEDs between them
# keep them apart.
EYES = [(9.0, 4.5), (15.0, 4.5)]
EYE_SIZE = (1.6, 1.05)
PUPIL_SIZE = (0.55, 1.05)
# Laughing eyes, squeezed into happy arcs: the LEDs (column, row) of ^ ^.
LAUGH_EYES = [(9, 5), (8, 4), (10, 4), (15, 5), (14, 4), (16, 4)]
# The mouth: a thin smile, along the bottom row with its corners turned
# up a row. Laughing, it opens: flat under the moustache, curving down
# to the bottom row, stretching wider with each ha.
SMILE_PTS = [(9.6, 0.45), (14.4, 0.45), (14.4, -0.45), (9.6, -0.45)]
SMILE_CORNERS = [(9.0, 1.0), (15.0, 1.0)]
LAUGH_PTS = [(9.0, 1.5), (15.0, 1.5), (14.2, 0.3), (12.8, -0.4), (11.2, -0.4), (9.8, 0.3)]
LAUGH_WIDE = (1.0, 0.12)       # laughing, the mouth this much wider, plus this at each ha
CRISP = 0.45                   # edge softness of the small features

# The face's features sit on a rounded head: those with a depth (how
# far out from the head's middle they are) slide round and squeeze as
# he turns his head, and go out of sight round the back.
HEAD_X = 12.0
PROFILE = 80.0                 # degrees his head is turned toward Rudolph
FACE_DEPTH = 6.4
BEARD_DEPTH = 3.0
NOSE_DEPTH = 7.4

GROUND_Y = -11.3


def _evergreen(x, scale, color):
    """An evergreen standing on the ground at x: trunk and three tiers."""
    def at(dx, dy):
        return (x + dx * scale, GROUND_Y + dy * scale)
    return [
        ("poly", TRUNK, [at(-1.2, 0), at(1.2, 0), at(1.2, 2.8), at(-1.2, 2.8)]),
        ("poly", color, [at(-8.0, 2.3), at(8.0, 2.3), at(0, 13.3)]),
        ("poly", color, [at(-6.5, 8.3), at(6.5, 8.3), at(0, 18.8)]),
        ("poly", color, [at(-5.0, 14.3), at(5.0, 14.3), at(0, 24.3)]),
    ]


# (kind, color, where[, depth]), drawn in this order, back to front:
# ellipses ("ellipse", or "crisp" for small features) are
# (x, y, rx, ry[, alpha]), polygons ("poly", "crisp poly") their corners.
WORLD = (
    [("poly", GROUND, [(-70, GROUND_Y), (110, GROUND_Y), (110, -40), (-70, -40)])]
    # Evergreens behind it all, clear of the close-up of his face: one at
    # each side, and a smaller one further back between the sleigh and
    # Rudolph.
    + _evergreen(33.0, 0.65, FAR_EVERGREEN) + _evergreen(-10.0, 1.0, EVERGREEN)
    + _evergreen(64.0, 1.0, EVERGREEN)
    + [
        # Rudolph, out in front: legs, tail, body, neck, head, antlers,
        # eye and that nose.
        ("poly", REINDEER, [(37.4, -5.0), (38.6, -5.0), (38.6, -10.9), (37.4, -10.9)]),
        ("poly", REINDEER, [(40.4, -5.0), (41.6, -5.0), (41.6, -10.9), (40.4, -10.9)]),
        ("poly", REINDEER, [(47.4, -5.0), (48.6, -5.0), (48.6, -10.9), (47.4, -10.9)]),
        ("poly", REINDEER, [(50.4, -5.0), (51.6, -5.0), (51.6, -10.9), (50.4, -10.9)]),
        ("ellipse", FUR, (36.4, -1.0, 1.1, 1.1)),
        ("ellipse", REINDEER, (44.0, -2.5, 7.6, 3.4)),
        ("poly", REINDEER, [(48.5, -0.8), (51.8, -1.8), (54.2, 3.4), (51.0, 4.6)]),
        ("poly", ANTLERS, [(51.0, 6.0), (52.6, 6.0), (50.6, 10.8), (49.0, 10.8)]),
        ("poly", ANTLERS, [(53.0, 6.0), (54.6, 6.0), (56.0, 10.8), (54.4, 10.8)]),
        ("ellipse", REINDEER, (53.4, 4.6, 3.0, 1.9)),
        ("ellipse", COAL, (53.8, 5.2, 0.45, 0.45)),
        ("ellipse", RUDOLPH, (56.6, 4.1, 1.1, 1.1)),
        # Santa, from the side: his soft hat, flopped over to the right
        # with the pom-pom hanging at the end...
        ("poly", RED, [(15.0, 11.0), (19.8, 9.0), (23.5, 4.8)]),
        ("ellipse", FUR, (24.2, 4.2, 1.6, 1.6)),
        ("poly", RED, [(5.8, 6.4), (18.2, 6.4), (19.0, 9.8), (11.0, 11.6)]),
        # ...his body, sitting low, and his arm reaching out to the front
        # of the sleigh...
        ("ellipse", RED, (11.0, -3.5, 6.8, 6.0)),
        ("poly", FUR, [(16.6, -0.5), (18.0, -1.5), (18.0, -8.0), (16.6, -8.0)]),
        ("ellipse", RED, (18.5, -1.8, 5.0, 2.3)),
        ("ellipse", MITTENS, (23.0, -2.3, 1.9, 1.9)),
        # ...his head: beard and hair, the face, then its features...
        ("ellipse", BEARD, (12.0, -1.0, 8.8, 5.0), BEARD_DEPTH),
        ("ellipse", BEARD, (5.6, 4.4, 1.3, 1.6)),
        ("ellipse", BEARD, (18.4, 4.4, 1.3, 1.6)),
        ("ellipse", SKIN, (12.0, 3.6, 6.4, 2.6)),
        ("ellipse", CHEEKS, (7.4, 3.0, 1.5, 0.8, 0.55), FACE_DEPTH),
        ("ellipse", CHEEKS, (16.6, 3.0, 1.5, 0.8, 0.55), FACE_DEPTH),
        ("crisp", EYE, EYES[0] + EYE_SIZE, FACE_DEPTH),
        ("crisp", EYE, EYES[1] + EYE_SIZE, FACE_DEPTH),
        ("crisp poly", MOUTH, SMILE_PTS, FACE_DEPTH),
        ("crisp", MOUTH, SMILE_CORNERS[0] + (0.45, 0.45), FACE_DEPTH),
        ("crisp", MOUTH, SMILE_CORNERS[1] + (0.45, 0.45), FACE_DEPTH),
        ("crisp", MOUSTACHE, (9.5, 2.0, 3.1, 0.75), FACE_DEPTH),
        ("crisp", MOUSTACHE, (14.5, 2.0, 3.1, 0.75), FACE_DEPTH),
        ("crisp", NOSE, (12.0, 3.0, 1.5, 0.65), NOSE_DEPTH),
        # ...the hat's soft fur trim: one row across his head, close up...
        ("ellipse", FUR, (12.0, 6.1, 6.6, 0.45)),
        # ...and the sleigh in front of him, hiding the bottom of his
        # beard, on gold runners.
        ("poly", SLEIGH, [(-9.0, 4.0), (-3.0, 3.0), (-3.0, -8.1), (-6.5, -8.1)]),
        ("poly", SLEIGH, [(-6.0, -2.0), (27.0, -2.0), (29.0, -8.1), (-4.5, -8.1)]),
        ("ellipse", SLEIGH, (29.5, -2.2, 3.0, 2.8)),
        ("poly", GOLD, [(-4.0, -9.9), (28.0, -9.9), (28.0, -10.9), (-4.0, -10.9)]),
        ("ellipse", GOLD, (29.5, -9.1, 1.9, 1.9)),
    ]
)

# The two views: zoom (LEDs per unit) and the world point at the middle
# of the mantle.
WIDE = (0.32, 24.5, 0.3)
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
# Close up, his eyes: (where the pupils look, -1 left .. 1 right, how
# long they stay), then HO HO HO.
LOOK_SCRIPT = [(0.0, 0.9), (-1.0, 1.2), (1.0, 1.2), (0.0, 1.2)]
LOOK_S = 0.25                  # moving from one to the next
BLINK_AT_S = 4.0               # one blink, looking back at you
BLINK_S = 0.3

# Snow, in three layers back to front: behind everything, in front of the
# trees but behind the sleigh, in front of it all. Each layer's
# (flakes, fall speed factor, how fast it spreads out as we zoom in);
# nearer flakes fall faster and spread more, so the layers look apart.
SNOW_LAYERS = ((7, 0.75, 0.5), (7, 1.0, 1.0), (6, 1.3, 1.5))
SNOW_FALL = (2.6, 4.2)         # rows/sec
SNOW_ALPHA = 0.1               # how much of the way to white a flake takes its LED
SNOW_FADE_S = 0.3              # going when his head starts turning, and coming back
SNOW_SWAY = 0.3                # columns
SNOW_SWAY_HZ = (0.2, 0.5)

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
        self.flies = color not in (GROUND, EVERGREEN, FAR_EVERGREEN, TRUNK)
        soft = CRISP if kind.startswith("crisp") else SOFT
        if kind.endswith("poly"):
            self.shape = Polygon(color, sides=len(where), soft=soft)
        else:
            self.shape = Ellipse(color, soft=soft)

    def place(self, zoom, cx, cy, turn=0.0, fly_x=0.0, fly_y=0.0):
        """Set the shape for a camera, with his head turned turn degrees
        toward Rudolph and the sleigh flown (fly_x, fly_y) from where it
        stands; it's hidden if it's off the mantle."""
        if self.flies:
            cx -= fly_x
            cy -= fly_y
        if self.kind.endswith("poly"):
            where, seen = self.where, 1.0
            if self.depth:
                # On the face: its corners slide round as he turns.
                where = [(turned(x, 0.0, self.depth, turn)[0], y) for x, y in where]
                seen = turned(HEAD_X, 0.0, self.depth, turn)[2]
            pts = [((x - cx) * zoom + 12.0, (y - cy) * zoom + 3.5) for x, y in where]
            on = (seen > 0 and max(x for x, _ in pts) > -1 and min(x for x, _ in pts) < COLS
                  and max(y for _, y in pts) > -1 and min(y for _, y in pts) < ROWS)
            if on:
                self.shape.set(pts, seen)
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
# SNOW
# ============================================================

class Snow:
    """Faint flakes drifting down, each shared between the two rows it's
    between so it glides, and mixed in over whatever is behind it so it
    takes on its color. They keep falling while hidden, so the snow picks
    up where it would be when it comes back."""

    def __init__(self):
        self.layers = [[self._new(random.uniform(0, ROWS), speed) for _ in range(n)]
                       for n, speed, _ in SNOW_LAYERS]
        self.color = to_light(SNOWFLAKE)
        self.t = 0.0
        self.alpha = 0.0         # nothing until fall() says so
        self.spread = 1.0        # how far we've zoomed in from the wide view

    def _new(self, y, speed):
        return [random.uniform(0, COLS - 1), y, speed * random.uniform(*SNOW_FALL),
                2 * math.pi * random.uniform(*SNOW_SWAY_HZ), random.uniform(0, 2 * math.pi)]

    def fall(self, t, dt, alpha):
        """Move every flake on; alpha (0..1) is how much they show."""
        self.t = t
        self.alpha = alpha
        for flakes, (_, speed, _) in zip(self.layers, SNOW_LAYERS):
            for i, f in enumerate(flakes):
                f[1] -= f[2] * dt
                if f[1] < -1.0:
                    flakes[i] = self._new(ROWS, speed)

    def draw(self, light, layer, behind=False, mask=None):
        """Draw one layer; behind: only on dark LEDs, so it's behind
        what's already there; mask: not on the LEDs it marks."""
        a0 = self.alpha * SNOW_ALPHA
        if a0 <= 0.0:
            return
        r, g, b = self.color
        s = self.spread ** SNOW_LAYERS[layer][2]
        t = self.t
        for f in self.layers[layer]:
            # Zooming in, flakes spread out from the middle, past us.
            x = 12.0 + (f[0] + SNOW_SWAY * math.sin(f[3] * t + f[4]) - 12.0) * s
            col = int(math.floor(x + 0.5))
            if not 0 <= col < COLS:
                continue
            y = 3.5 + (f[1] - 3.5) * s
            row = int(math.floor(y))
            up = y - row
            for rr, w in ((row, 1.0 - up), (row + 1, up)):
                if 0 <= rr < ROWS and w > 0.0:
                    i = rr * COLS + col
                    if mask and mask[i]:
                        continue
                    o = 3 * i
                    vr, vg, vb = light[o], light[o + 1], light[o + 2]
                    if behind and (vr or vg or vb):
                        continue
                    a = int(256 * a0 * w)
                    light[o] = vr + (((r - vr) * a) >> 8)
                    light[o + 1] = vg + (((g - vg) * a) >> 8)
                    light[o + 2] = vb + (((b - vb) * a) >> 8)


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def santa(strips):
    canvas = Canvas(strips)
    light = canvas.light
    parts = [Part(*part) for part in WORLD]
    # The ground and trees are at the back of the world, so drawing them
    # first keeps the order.
    still = [part for part in parts if not part.flies]
    flying = [part for part in parts if part.flies]
    pupils = [Ellipse(PUPIL, soft=CRISP) for _ in EYES]
    lids = [Ellipse(SKIN, soft=CRISP) for _ in EYES]
    lashes = [Ellipse(LASH, soft=CRISP) for _ in EYES]
    laugh_cheeks = [Ellipse(CHEEKS, x, 3.0, 1.6, 0.9, 0.6) for x in (7.4, 16.6)]
    laugh_mouth = Polygon(MOUTH, sides=len(LAUGH_PTS), soft=CRISP)
    snow = Snow()
    last_t = 0.0
    script_s = sum(hold for _, hold in LOOK_SCRIPT)

    backdrop = None              # the ground and trees in the wide view

    def paint(f, turn=0.0, with_pupils=True, fly_x=0.0, fly_y=0.0):
        zoom, cx, cy = _view(f)
        snow.spread = zoom / WIDE[0]
        # In the wide view only the sleigh moves: the rest is painted once.
        # Snow goes behind it all, then between the trees and the sleigh,
        # then in front.
        if f == 0.0 and backdrop:
            light[:] = backdrop
            snow.draw(light, 0, behind=True)
        else:
            canvas.clear()
            snow.draw(light, 0)
            for part in still:
                part.place(zoom, cx, cy, turn, fly_x, fly_y)
                part.draw(light)
        snow.draw(light, 1)
        for part in flying:
            part.place(zoom, cx, cy, turn, fly_x, fly_y)
            part.draw(light)
        if with_pupils:
            for pupil, (x, y) in zip(pupils, EYES):
                x, rx, seen = turned(x, PUPIL_SIZE[0], FACE_DEPTH, turn)
                pupil.set((x + fly_x - cx) * zoom + 12.0, (y + fly_y - cy) * zoom + 3.5,
                          rx * zoom, PUPIL_SIZE[1] * zoom, seen)
                pupil.draw(light)
        snow.draw(light, 2)

    # The still views, painted once.
    canvas.clear()
    for part in still:
        part.place(*_view(0.0))
        part.draw(light)
    backdrop = array.array("H", light)
    # The sleigh parked in the wide view, and which LEDs it's on, so the
    # snow between it and the trees can go behind it.
    paint(0.0, PROFILE)
    wide = array.array("H", light)
    on_sleigh = bytearray(ROWS * COLS)
    for i in range(ROWS * COLS):
        o = 3 * i
        on_sleigh[i] = 1 if wide[o:o + 3] != backdrop[o:o + 3] else 0
    paint(1.0)
    face_open = array.array("H", light)
    paint(1.0, 0.0, with_pupils=False)
    face = array.array("H", light)

    ho = HoHoHo()
    scene_start = utime.ticks_ms()
    # The cycle: land, wide, zoom in, close up, HO HO HO, laugh, zoom out,
    # take off.
    phases = ("land", "wide", "in", "close", "ho", "laugh", "out", "takeoff")
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
                hold = script_s
        what = phases[phase]
        age = t - start
        dt = min(0.1, t - last_t)
        last_t = t

        # Snow while the sleigh's side on, gone as soon as he starts to
        # turn his head, back once he's turned back.
        if what in ("land", "wide", "takeoff"):
            snow_on = 1.0
        elif what == "in":
            snow_on = 1.0 - (age - TURN_START_S) / SNOW_FADE_S
        elif what == "out":
            snow_on = (age - (ZOOM_S - TURN_START_S)) / SNOW_FADE_S
        else:
            snow_on = 0.0
        snow.fall(t, dt, max(0.0, min(1.0, snow_on)))

        if what == "wide":
            light[:] = wide
            snow.draw(light, 0, behind=True)
            snow.draw(light, 1, mask=on_sleigh)
            snow.draw(light, 2)
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
            stretch = LAUGH_WIDE[0] + LAUGH_WIDE[1] * abs(math.sin(math.pi * LAUGH_HZ * age))
            laugh_mouth.set([(HEAD_X + (x - HEAD_X) * stretch, y) for x, y in LAUGH_PTS])
            laugh_mouth.draw(light)
        else:
            # Close up: the eyes follow the script, with one blink.
            look_x = 0.0
            at = 0.0
            for i, (x, hold_s) in enumerate(LOOK_SCRIPT):
                if age < at + hold_s or i == len(LOOK_SCRIPT) - 1:
                    before = LOOK_SCRIPT[i - 1][0] if i else 0.0
                    look_x = before + (x - before) * ease((age - at) / LOOK_S)
                    break
                at += hold_s
            g = age - BLINK_AT_S
            opened = 1.0 - math.sin(math.pi * g / BLINK_S) if 0.0 <= g < BLINK_S else 1.0
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
