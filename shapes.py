"""Soft-edged shapes painted onto a canvas.Canvas, for scenes drawn as
pictures: faces, hats, trees.

Each shape is set from floats in LED spacings (x = column, y = row, 0 at
the bottom) and painted over what's there, every LED mixed by how much
of it the shape covers, so shapes glide smoothly between LEDs. The
painting is viper integer code in Q8 fixed point (see canvas.py).

Shapes keep their parameters in an array, so a shape that doesn't move
costs nothing to set up each frame: set it once, draw it every frame.
"""
import array
import math
import micropython
from canvas import q8, to_light
from grid import ROWS, COLS

SOFT = 0.8                     # edge softness: LED spacings from full to off

# sqrt(q / 256) in Q8, for ellipse edges.
_ROOTS = array.array("H", [int(256 * math.sqrt(q / 256) + 0.5) for q in range(2048)])


def ease(t):
    """0..1 eased in and out."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3 - 2 * t)


@micropython.viper
def _ellipse(light: ptr16, roots: ptr16, p: ptr32):
    """Paint an ellipse; p is from Ellipse.set()."""
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
    col_lo = p[10]
    col_hi = p[11]
    row = p[12]
    row_hi = p[13]
    alpha = p[14]
    while row <= row_hi:
        oy = (((row << 8) - y) * inv_ry) >> 8
        col = col_lo
        while col <= col_hi:
            ox = (((col << 8) - x) * inv_rx) >> 8
            q = (ox * ox + oy * oy) >> 8
            if q < 2048:
                # Distance in from the edge, in LEDs (close enough for
                # ellipses this round).
                a = (((((256 - int(roots[q + 0])) * rm) >> 8) * inv_soft) >> 8) + 128
                if a > 0:
                    if a > 256:
                        a = 256
                    a = (a * alpha) >> 8
                    o = (row * cols + col) * 3
                    v = int(light[o + 0])
                    light[o + 0] = v + (((cr - v) * a) >> 8)
                    v = int(light[o + 1])
                    light[o + 1] = v + (((cg - v) * a) >> 8)
                    v = int(light[o + 2])
                    light[o + 2] = v + (((cb - v) * a) >> 8)
            col += 1
        row += 1


@micropython.viper
def _polygon(light: ptr16, p: ptr32):
    """Paint a convex polygon; p is from Polygon.set(): its edges are
    lines (nx, ny, c), each LED's distance inside one being
    nx * x + ny * y + c."""
    cols = p[0]
    col_lo = p[1]
    col_hi = p[2]
    row = p[3]
    row_hi = p[4]
    inv_soft = p[5]
    cr = p[6]
    cg = p[7]
    cb = p[8]
    alpha = p[9]
    end = 11 + p[10] * 3
    while row <= row_hi:
        y = row << 8
        col = col_lo
        while col <= col_hi:
            x = col << 8
            # Distance inside the nearest edge.
            m = 1 << 20
            k = 11
            while k < end:
                d = ((p[k + 0] * x + p[k + 1] * y) >> 8) + p[k + 2]
                if d < m:
                    m = d
                k += 3
            a = ((m * inv_soft) >> 8) + 128
            if a > 0:
                if a > 256:
                    a = 256
                a = (a * alpha) >> 8
                o = (row * cols + col) * 3
                v = int(light[o + 0])
                light[o + 0] = v + (((cr - v) * a) >> 8)
                v = int(light[o + 1])
                light[o + 1] = v + (((cg - v) * a) >> 8)
                v = int(light[o + 2])
                light[o + 2] = v + (((cb - v) * a) >> 8)
            col += 1
        row += 1


def _span(lo, hi, size):
    """The LEDs (first, last) a shape from lo to hi can touch."""
    first = max(0, int(math.floor(lo - SOFT)))
    last = min(size - 1, int(math.ceil(hi + SOFT)))
    return first, last


class Ellipse:
    def __init__(self, color, x=0.0, y=0.0, rx=1.0, ry=1.0, alpha=1.0, soft=SOFT):
        """soft: edge softness in LED spacings; small features read
        better a little crisper than SOFT."""
        self.p = array.array("i", [0] * 15)
        self.p[5] = int(256 / soft)
        self.p[9] = COLS
        self.last = None
        self.color(color)
        self.set(x, y, rx, ry, alpha)

    def color(self, color):
        self.p[6], self.p[7], self.p[8] = to_light(color)

    def set(self, x, y, rx, ry, alpha=1.0):
        # Most shapes sit still most of the time: nothing to redo.
        args = (x, y, rx, ry, alpha)
        if args == self.last:
            return
        self.last = args
        p = self.p
        self.shown = alpha > 0.004 and rx > 0.05 and ry > 0.05
        if not self.shown:
            return
        p[0] = q8(x)
        p[1] = q8(y)
        p[2] = int(256 / rx)
        p[3] = int(256 / ry)
        p[4] = q8(min(rx, ry))
        p[10], p[11] = _span(x - rx, x + rx, COLS)
        p[12], p[13] = _span(y - ry, y + ry, ROWS)
        p[14] = int(256 * alpha + 0.5)

    def draw(self, light):
        if self.shown:
            _ellipse(light, _ROOTS, self.p)


class Polygon:
    def __init__(self, color, points=None, alpha=1.0, sides=4, soft=SOFT):
        self.p = array.array("i", [0] * (11 + 3 * sides))
        self.p[0] = COLS
        self.p[5] = int(256 / soft)
        self.last = None
        self.color(color)
        self.shown = False
        if points:
            self.set(points, alpha)

    def color(self, color):
        self.p[6], self.p[7], self.p[8] = to_light(color)

    def set(self, points, alpha=1.0):
        """points: the corners of a convex polygon, in either order."""
        if (points, alpha) == self.last:
            return
        self.last = (points, alpha)
        p = self.p
        self.shown = alpha > 0.004
        if not self.shown:
            return
        n = len(points)
        cx = sum(x for x, _ in points) / n
        cy = sum(y for _, y in points) / n
        k = 11
        for i in range(n):
            ax, ay = points[i]
            bx, by = points[(i + 1) % n]
            nx, ny = ay - by, bx - ax
            length = math.sqrt(nx * nx + ny * ny)
            nx, ny = nx / length, ny / length
            # Point the normal inward.
            if nx * (cx - ax) + ny * (cy - ay) < 0:
                nx, ny = -nx, -ny
            p[k] = q8(nx)
            p[k + 1] = q8(ny)
            p[k + 2] = -q8(nx * ax + ny * ay)
            k += 3
        p[10] = n
        p[1], p[2] = _span(min(x for x, _ in points), max(x for x, _ in points), COLS)
        p[3], p[4] = _span(min(y for _, y in points), max(y for _, y in points), ROWS)
        p[9] = int(256 * alpha + 0.5)

    def draw(self, light):
        if self.shown:
            _polygon(light, self.p)
