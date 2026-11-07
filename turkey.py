import array
import math
import micropython
import random
import utime
from canvas import Canvas, q8, to_light
from grid import ROWS, COLS

# ============================================================
# CONFIGURATION
# ============================================================
# A front-on turkey: round body, head with eyes, beak and wattle, and a
# tail fan behind that opens, quivers and closes again. Everything is
# drawn from shapes in continuous space, each LED lit by how much of it
# a shape covers, so the tail and head glide smoothly between LEDs.
#
# Colors are as they'd look with gamma off; the scene mixes them in real
# light and gamma-encodes each LED at the end.

BODY_COLOR = (70, 22, 2)
HEAD_COLOR = (90, 30, 3)
EYE_COLOR = (200, 200, 170)
BEAK_COLOR = (255, 150, 0)
WATTLE_COLOR = (255, 0, 0)
LEG_COLOR = (180, 70, 0)
BLACK = (0, 0, 0)

# The tail's color bands, from the root out: each starts this far along
# the feathers (as a fraction of their length). They make the fan's
# rainbow arcs.
TAIL_BANDS = [
    (0.0, (210, 0, 0)),        # red
    (0.52, (255, 60, 0)),      # orange
    (0.76, (255, 160, 0)),     # yellow
]
FEATHERS = 9
FEATHER_SHADES = (1.0, 0.7)    # alternate feathers a little darker

# Shapes, in LED spacings: x = column, y = row (0 = bottom).
CENTER_X = 12.0
BODY_Y = 2.3                   # body ellipse center...
BODY_RX = 2.9                  # ...and half-width / half-height
BODY_RY = 2.0
HEAD_Y = 5.3                   # head center when not bobbing
HEAD_R = 1.25
EYE_DX = 0.95                  # eyes either side of center, above it
EYE_DY = 0.55
EYE_R = 0.45
BEAK_DY = -0.15
BEAK_R = 0.5
WATTLE_DX = 0.35               # hangs below the beak, a bit to one side
WATTLE_DY = -1.05
WATTLE_R = 0.5
LEGS = ((11.0, 0.0), (13.0, 0.0))
LEG_R = 0.5

FAN_Y = 2.6                    # the point the feathers spread from
FAN_ASPECT = 1.45              # stretch sideways to fill the wide grid
FAN_SPREAD = (35.0, 160.0)     # degrees, closed and fully open
FAN_LENGTH = (5.2, 7.6)        # feather length, closed and open
FEATHER_GAP = 0.55             # how dark the lines between feathers get
SOFT = 0.9                     # edge softness: LED spacings from full to off
OUTLINE = 0.7                  # dark ring around the body and head

# Timing, in seconds.
CLOSED_S = (2.0, 4.0)          # tail down between displays
OPEN_S = 1.6                   # fanning out...
DISPLAY_S = (4.0, 7.0)         # ...showing off...
CLOSE_S = 1.4                  # ...and folding back up
QUIVER_S = 0.9                 # tail rattle once it's open
QUIVER_HZ = 9.0
QUIVER_DEG = 4.0
SWAY_DEG = 7.0                 # slow side to side turn of the open fan
SWAY_HZ = 0.18
GOBBLE_EVERY_S = (3.0, 7.0)
GOBBLE_S = 0.9
GOBBLE_HZ = 5.0                # head bobs per second while gobbling
GOBBLE_BOB = 0.55              # rows
GLANCE_EVERY_S = (1.5, 4.0)    # head turns to look left / right
GLANCE_S = 0.5
GLANCE_DX = 0.6                # columns

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# DRAWING
# ============================================================
# Drawn on a canvas.Canvas in real light (see canvas.py); the per-LED work
# is viper integer code in Q8 fixed point.


def _ease(t):
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3 - 2 * t)


@micropython.viper
def _draw_tail(light: ptr16, cells: ptr32, n_cells: int, p: ptr32, bands: ptr32):
    """Paint the fan into light[].

    cells holds (light index, distance, angle) of each LED the body
    doesn't hide, measured from the fan's root; p the fan's shape this
    frame (see _tail_params); bands the colors (start, r, g, b).
    """
    half = p[0]
    spacing = p[1]
    inv_spacing = p[2]
    spacing_rad = p[3]
    tilt = p[4]
    length = p[5]
    n = p[6]
    n_bands = p[7]
    inv_soft = p[8]
    gap = p[9]
    shade_lo = p[10]
    edge = half + (spacing >> 1)              # outside edge of the fan
    c = 0
    while c < n_cells * 3:
        o = cells[c]
        r = cells[c + 1]
        a = cells[c + 2] - tilt
        c += 3
        # Which feather, as a fraction, and how far across it (-128..128).
        u = ((a + half) * inv_spacing) >> 16
        k = (u + 128) >> 8
        if k < 0:
            k = 0
        elif k > n - 1:
            k = n - 1
        ad = u - (k << 8)
        if ad < 0:
            ad = -ad
        # Gaps, shading and rounded tips only once feathers are far
        # enough apart to see (arc = LEDs between them here); folded up,
        # they're one bundle.
        arc = (spacing_rad * r) >> 16
        sep = ((arc * 171) >> 8) - 77         # arc / 1.5 - 0.3
        if sep < 0:
            sep = 0
        elif sep > 256:
            sep = 256
        # Coverage: inside the fan's sides and the feather tips.
        aa = a if a >= 0 else -a
        side = ((((edge - aa) * 1144) >> 16) * r) >> 8   # degrees -> LEDs
        tip = (length * (256 - ((((184 * sep) >> 8) * ((ad * ad) >> 8)) >> 8))) >> 8
        e1 = ((side * inv_soft) >> 8) + 128
        if e1 <= 0:
            continue
        if e1 > 256:
            e1 = 256
        e2 = (((tip - r) * inv_soft) >> 8) + 128
        if e2 <= 0:
            continue
        if e2 > 256:
            e2 = 256
        cover = (e1 * e2) >> 8
        g = (ad - 77) * 5
        if g > 0:
            if g > 256:
                g = 256
            cover = (cover * (256 - ((((gap * sep) >> 8) * g) >> 8))) >> 8
        # Alternate feathers shaded, blended half way at the gap.
        if k & 1:
            shade = shade_lo
            other = 256
        else:
            shade = 256
            other = shade_lo
        w = ((ad - 77) * 5) >> 1
        if w > 0:
            if w > 128:
                w = 128
            shade += ((other - shade) * w) >> 8
        cover = (cover * (256 + (((shade - 256) * sep) >> 8))) >> 8
        # Color band, blending into the next across SOFT.
        cr = bands[1]
        cg = bands[2]
        cb = bands[3]
        b = 4
        while b < n_bands * 4:
            t = (((r - ((bands[b] * length) >> 8)) * inv_soft) >> 8) + 128
            if t <= 0:
                break
            if t > 256:
                t = 256
            cr += ((bands[b + 1] - cr) * t) >> 8
            cg += ((bands[b + 2] - cg) * t) >> 8
            cb += ((bands[b + 3] - cb) * t) >> 8
            b += 4
        light[o] = (cr * cover) >> 8
        light[o + 1] = (cg * cover) >> 8
        light[o + 2] = (cb * cover) >> 8


@micropython.viper
def _disc(light: ptr16, roots: ptr16, p: ptr32):
    """Paint an ellipse over light[], partly covered LEDs mixed in.
    p is from _disc_params; roots[q] = sqrt(q) in Q8."""
    x = p[0]
    y = p[1]
    inv_rx = p[2]
    inv_ry = p[3]
    rm = p[4]
    inv_soft = p[5]
    cr = p[6]
    cg = p[7]
    cb = p[8]
    cols = p[9]
    x_lo = (p[10] - 256) >> 8
    x_hi = (p[11] + 511) >> 8
    y_lo = (p[12] - 256) >> 8
    y_hi = (p[13] + 511) >> 8
    if x_lo < 0:
        x_lo = 0
    if y_lo < 0:
        y_lo = 0
    if x_hi > cols - 1:
        x_hi = cols - 1
    if y_hi > p[14] - 1:
        y_hi = p[14] - 1
    row = y_lo
    while row <= y_hi:
        oy = (((row << 8) - y) * inv_ry) >> 8
        col = x_lo
        while col <= x_hi:
            ox = (((col << 8) - x) * inv_rx) >> 8
            q = (ox * ox + oy * oy) >> 8
            if q < 2048:
                # Distance to the edge in LEDs (close enough for ellipses
                # this round).
                a = (((((256 - roots[q]) * rm) >> 8) * inv_soft) >> 8) + 128
                if a > 0:
                    if a > 256:
                        a = 256
                    o = (row * cols + col) * 3
                    v = int(light[o])
                    light[o] = v + (((cr - v) * a) >> 8)
                    v = int(light[o + 1])
                    light[o + 1] = v + (((cg - v) * a) >> 8)
                    v = int(light[o + 2])
                    light[o + 2] = v + (((cb - v) * a) >> 8)
            col += 1
        row += 1


def _disc_params(p, x, y, rx, ry, color):
    """Fill p (array 'i', 15 long) with a disc for _disc()."""
    p[0] = q8(x)
    p[1] = q8(y)
    p[2] = int(256 / rx)
    p[3] = int(256 / ry)
    p[4] = q8(min(rx, ry))
    p[5] = int(256 / SOFT)
    p[6], p[7], p[8] = to_light(color)
    p[9] = COLS
    p[10] = q8(x - rx)
    p[11] = q8(x + rx)
    p[12] = q8(y - ry)
    p[13] = q8(y + ry)
    p[14] = ROWS
    return p


# ============================================================
# MOTION
# ============================================================

class Tail:
    """How open the fan is: closed -> opening -> display -> closing."""

    def __init__(self, t):
        self.phase = 0
        self.start = t
        self.hold = random.uniform(*CLOSED_S)

    def openness(self, t):
        """0..1 open, and seconds since it finished opening (or None)."""
        age = t - self.start
        if self.phase == 0 and age >= self.hold:
            self._next(t, 1, OPEN_S)
        elif self.phase == 1 and age >= OPEN_S:
            self._next(t, 2, random.uniform(*DISPLAY_S))
        elif self.phase == 2 and age >= self.hold:
            self._next(t, 3, CLOSE_S)
        elif self.phase == 3 and age >= CLOSE_S:
            self._next(t, 0, random.uniform(*CLOSED_S))
        age = t - self.start
        if self.phase == 0:
            return 0.0, None
        if self.phase == 1:
            return _ease(age / OPEN_S), None
        if self.phase == 2:
            return 1.0, age
        return 1.0 - _ease(age / CLOSE_S), None

    def _next(self, t, phase, hold):
        self.phase = phase
        self.start = t
        self.hold = hold


class Head:
    """Gobbles (quick bobs) and glances left and right."""

    def __init__(self, t):
        self.gobble_at = t + random.uniform(*GOBBLE_EVERY_S)
        self.glance_at = t + random.uniform(*GLANCE_EVERY_S)
        self.glance_start = t
        self.look_from = 0.0
        self.look_to = 0.0

    def offset(self, t):
        """(dx, dy) of the head, and how hard it's gobbling (0..1)."""
        g = t - self.gobble_at
        dy = 0.0
        gobble = 0.0
        if g >= GOBBLE_S:
            self.gobble_at = t + random.uniform(*GOBBLE_EVERY_S)
        elif g >= 0.0:
            gobble = math.sin(math.pi * g / GOBBLE_S)
            dy = -GOBBLE_BOB * gobble * abs(math.sin(math.pi * GOBBLE_HZ * g))
        if t >= self.glance_at:
            self.look_from = self.look_to
            # From the side, mostly look back to the middle.
            if self.look_to != 0.0 and random.random() < 0.7:
                self.look_to = 0.0
            else:
                self.look_to = random.choice((-GLANCE_DX, GLANCE_DX))
            self.glance_start = t
            self.glance_at = t + GLANCE_S + random.uniform(*GLANCE_EVERY_S)
        s = (t - self.glance_start) / GLANCE_S
        dx = self.look_from + (self.look_to - self.look_from) * _ease(s)
        return dx, dy, gobble


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def turkey(strips):
    canvas = Canvas(strips)
    roots = array.array("H", [int(256 * math.sqrt(q / 256) + 0.5) for q in range(2048)])

    # Every LED's distance and angle from the fan's root (angle 0 is
    # straight up), skipping the ones the body always hides.
    cells = []
    for row in range(ROWS):
        for col in range(COLS):
            dx = (col - CENTER_X) / FAN_ASPECT
            dy = row - FAN_Y
            bx = (col - CENTER_X) / BODY_RX
            by = (row - BODY_Y) / BODY_RY
            if math.sqrt(bx * bx + by * by) < 1.0 - SOFT / min(BODY_RX, BODY_RY):
                continue
            cells += (3 * (row * COLS + col), q8(math.sqrt(dx * dx + dy * dy)),
                      q8(math.degrees(math.atan2(dx, dy))))
    n_cells = len(cells) // 3
    cells = array.array("i", cells)
    bands = []
    for at, color in TAIL_BANDS:
        bands.append(q8(at))
        bands += to_light(color)
    bands = array.array("i", bands)

    # The fan's shape: the entries that change are set every frame.
    tail_p = array.array("i", [0] * 11)
    tail_p[6] = FEATHERS
    tail_p[7] = len(TAIL_BANDS)
    tail_p[8] = int(256 / SOFT)
    tail_p[9] = q8(FEATHER_GAP)
    tail_p[10] = q8(FEATHER_SHADES[1] / FEATHER_SHADES[0])

    def disc(x, y, rx, ry, color):
        return _disc_params(array.array("i", [0] * 15), x, y, rx, ry, color)

    still = [disc(x, y, LEG_R, LEG_R, LEG_COLOR) for x, y in LEGS]
    still.append(disc(CENTER_X, BODY_Y, BODY_RX + OUTLINE, BODY_RY + OUTLINE, BLACK))
    still.append(disc(CENTER_X, BODY_Y, BODY_RX, BODY_RY, BODY_COLOR))
    head_p = [array.array("i", [0] * 15) for _ in range(6)]

    light = canvas.light

    scene_start = utime.ticks_ms()
    tail = Tail(0.0)
    head = Head(0.0)

    while True:
        frame_start = utime.ticks_ms()
        # Time is measured from scene start: the Pico's floats are single
        # precision, so raw ticks_ms() seconds get coarse after days of uptime.
        t = utime.ticks_diff(frame_start, scene_start) / 1000

        o, shown = tail.openness(t)
        spread = FAN_SPREAD[0] + (FAN_SPREAD[1] - FAN_SPREAD[0]) * o
        length = FAN_LENGTH[0] + (FAN_LENGTH[1] - FAN_LENGTH[0]) * o
        tilt = SWAY_DEG * o * math.sin(2 * math.pi * SWAY_HZ * t)
        if shown is not None and shown < QUIVER_S:
            q = 1.0 - shown / QUIVER_S
            spread += QUIVER_DEG * q * math.sin(2 * math.pi * QUIVER_HZ * shown)
        spacing = spread / (FEATHERS - 1)
        tail_p[0] = q8(spread / 2)
        tail_p[1] = q8(spacing)
        tail_p[2] = int(65536 / spacing)
        tail_p[3] = int(spacing * math.pi / 180 * 65536)
        tail_p[4] = q8(tilt)
        tail_p[5] = q8(length)

        hx, hy, gobble = head.offset(t)
        hx += CENTER_X
        hy += HEAD_Y
        # The wattle swings while gobbling.
        wx = hx + WATTLE_DX * (1.0 - 2.0 * gobble * math.sin(2 * math.pi * GOBBLE_HZ * t))
        _disc_params(head_p[0], hx, hy, HEAD_R + OUTLINE, HEAD_R + OUTLINE, BLACK)
        _disc_params(head_p[1], hx, hy, HEAD_R, HEAD_R, HEAD_COLOR)
        _disc_params(head_p[2], hx - EYE_DX, hy + EYE_DY, EYE_R, EYE_R, EYE_COLOR)
        _disc_params(head_p[3], hx + EYE_DX, hy + EYE_DY, EYE_R, EYE_R, EYE_COLOR)
        _disc_params(head_p[4], wx, hy + WATTLE_DY, WATTLE_R, WATTLE_R * 1.3, WATTLE_COLOR)
        _disc_params(head_p[5], hx, hy + BEAK_DY, BEAK_R, BEAK_R, BEAK_COLOR)

        canvas.clear()
        _draw_tail(light, cells, n_cells, tail_p, bands)
        for p in still:
            _disc(light, roots, p)
        for p in head_p:
            _disc(light, roots, p)
        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
