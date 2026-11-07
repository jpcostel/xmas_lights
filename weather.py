import array
import math
import micropython
import random
import select
import sys
import utime
from canvas import Canvas, LIGHT, PERM, drift, noise, q8, to_light
from grid import ROWS, COLS

# ============================================================
# CONFIGURATION
# ============================================================
# The weather outside, live. weather_service.py on the Pi works out how
# it should look and sends it here as lines like
#     #WX top=1,2,12 cloud=0.42 rain=2.5 ...
# while this runs; the scene eases toward each new look. Until the
# first arrives it shows a clear night.

EASE_S = 15.0                  # seconds to settle most of the way to a new look

CLOUD_WIDTH = 6.0              # columns across a cloud...
CLOUD_HEIGHT = 2.5             # ...and rows
CLOUD_EDGE = 0.25              # how soft their edges are (0-1)
CLOUD_SHADE = 0.25             # thicker parts of a cloud this much darker
CLOUD_DRIFT = 0.08             # columns/sec per m/s of wind across the mantle
CLOUD_CREEP = 0.04             # columns/sec they drift even on a still day
CLOUD_CHANGE = 0.03            # how quickly they change shape

STARS = 30
STAR_LEVEL = (12, 70)          # dimmest and brightest (0-255, gamma off)
STAR_COLOR = (255, 235, 210)
STAR_LOWEST_ROW = 2            # none right down at the horizon
TWINKLE_HZ = 0.8

RAIN_PER_MM = 10               # drops/sec for 1 mm/h (more for heavier rain)
RAIN_MOST = 70                 # drops on the mantle at once, at most
RAIN_SPEED = (13.0, 17.0)      # rows/sec
RAIN_STREAK = 1.6              # rows long
RAIN_FALL_MS = 9.0             # real falling speed (m/s), to slant drops with the wind
SPLASH_S = 0.18
SPLASH = 0.5                   # splash brightness, as a fraction of the drop's

SNOW_PER_CM = 9                # flakes/sec for 1 cm/h (more for heavier snow)
SNOW_MOST = 80
SNOW_SPEED = (1.0, 2.0)        # rows/sec
SNOW_DRIFT = 0.35              # columns/sec per m/s of wind across the mantle
SNOW_SWAY = (0.2, 0.6)         # columns
SNOW_SWAY_HZ = (0.3, 0.8)
SNOW_SETTLE_S = 2.0            # flakes rest on the bottom row this long, fading

LIGHTNING_PER_MIN = 4          # in a thunderstorm
FLASH_COLOR = (200, 200, 255)
FLASH_S = 0.7                  # a strike's flickers last this long

FRAME_MS = 16                  # ~60 FPS

# The look until the Pi says otherwise: a clear night.
CLEAR_NIGHT = {
    "top": [0.0, 0.0, 0.0], "bottom": [0.0, 0.0, 0.0],
    "cloud": [0.1], "cloud_color": [0.0, 0.0, 0.0], "stars": [1.0],
    "rain": [0.0], "snow": [0.0], "storm": [0.0], "wind": [0.0, 0.0],
    "rain_color": [70.0, 85.0, 120.0], "snow_color": [110.0, 110.0, 125.0],
}


# ============================================================
# MESSAGES FROM THE PI
# ============================================================

class Inbox:
    """Lines arriving on the serial input, read without waiting."""

    def __init__(self):
        self.poll = select.poll()
        self.poll.register(sys.stdin, select.POLLIN)
        self.partial = ""

    def lines(self):
        out = []
        while self.poll.poll(0):
            ch = sys.stdin.read(1)
            if ch == "\r" or ch == "\n":
                if self.partial:
                    out.append(self.partial)
                self.partial = ""
            elif len(self.partial) < 600:
                self.partial += ch
        return out


def parse(line):
    """{key: [numbers]} from a #WX line, or None for any other line."""
    if not line.startswith("#WX "):
        return None
    look = {}
    for part in line[4:].split():
        key, _, value = part.partition("=")
        try:
            look[key] = [float(v) for v in value.split(",")]
        except ValueError:
            pass
    return look


class Look:
    """The look being shown, easing toward the latest from the Pi."""

    def __init__(self):
        self.now = {k: list(v) for k, v in CLEAR_NIGHT.items()}
        self.want = {k: list(v) for k, v in CLEAR_NIGHT.items()}
        self.heard = False

    def receive(self, look):
        for key, values in look.items():
            self.want[key] = values
            # The first look shows at once; a new key starts where it's going.
            if not self.heard or key not in self.now or len(self.now[key]) != len(values):
                self.now[key] = list(values)
        self.heard = True

    def ease(self, dt):
        f = min(1.0, dt / EASE_S * 3)
        for key, want in self.want.items():
            now = self.now[key]
            for i in range(len(want)):
                now[i] += (want[i] - now[i]) * f

    def get(self, key, i=0):
        v = self.now.get(key)
        return v[i] if v and i < len(v) else 0.0


# ============================================================
# DRAWING
# ============================================================

@micropython.viper
def _sky(light: ptr16, perm, p: ptr32, sky: ptr16, stars: ptr8):
    """Fill light[] with the sky (sky[] holds each row's color), the
    clouds over it and the stars showing through. p holds the clouds'
    scale, position, cover, color and shading, and the stars' twinkle
    and color."""
    cols = p[0]
    rows = p[1]
    sx = p[2]
    sy = p[3]
    cx = p[4]
    cy = p[5]
    thresh = p[6]
    soft = p[7]
    cr = p[8]
    cg = p[9]
    cb = p[10]
    tw = p[11]
    shine = p[12]
    wr = p[13]
    wg = p[14]
    wb = p[15]
    shade = p[16]
    top = 255 * 16
    o = 0
    i = 0
    row = 0
    while row < rows:
        br = int(sky[row * 3])
        bg = int(sky[row * 3 + 1])
        bb = int(sky[row * 3 + 2])
        col = 0
        while col < cols:
            n1 = int(noise(col * sx + cx, row * sy + cy, perm))
            n2 = int(noise(col * sx * 2 + cx * 2 + 30000, row * sy * 2 + cy + 20000, perm))
            d = ((((n1 * 180 + n2 * 76) >> 8) - thresh) * soft) >> 8
            if d < 0:
                d = 0
            elif d > 256:
                d = 256
            # Thicker cloud is darker.
            k = 256 - ((shade * n1) >> 8)
            r = br + (((((cr * k) >> 8) - br) * d) >> 8)
            g = bg + (((((cg * k) >> 8) - bg) * d) >> 8)
            b = bb + (((((cb * k) >> 8) - bb) * d) >> 8)
            s = int(stars[i + 0])
            if s > 0:
                if d < 256:
                    t = int(noise(tw, i * 2560 + 40000, perm))
                    a = (((((s * (64 + t)) >> 8) * shine) >> 8) * (256 - d)) >> 8
                    r += (wr * a) >> 8
                    g += (wg * a) >> 8
                    b += (wb * a) >> 8
            light[o + 0] = r if r < top else top
            light[o + 1] = g if g < top else top
            light[o + 2] = b if b < top else top
            o += 3
            i += 1
            col += 1
        row += 1


@micropython.viper
def _add2(light: ptr16, cols: int, row: int, x: int, r: int, g: int, b: int):
    """Add a color at Q8 column x of a row, shared between the two
    columns either side of it."""
    top = 255 * 16
    col = x >> 8
    right = x & 255
    left = 256 - right
    o = 3 * (row * cols + col)
    if col >= 0:
        if col < cols:
            v = int(light[o + 0]) + ((r * left) >> 8)
            light[o + 0] = v if v < top else top
            v = int(light[o + 1]) + ((g * left) >> 8)
            light[o + 1] = v if v < top else top
            v = int(light[o + 2]) + ((b * left) >> 8)
            light[o + 2] = v if v < top else top
    if col + 1 >= 0:
        if col + 1 < cols:
            v = int(light[o + 3]) + ((r * right) >> 8)
            light[o + 3] = v if v < top else top
            v = int(light[o + 4]) + ((g * right) >> 8)
            light[o + 4] = v if v < top else top
            v = int(light[o + 5]) + ((b * right) >> 8)
            light[o + 5] = v if v < top else top


@micropython.viper
def _streaks(light: ptr16, drops: ptr32, n: int, p: ptr32):
    """Add falling streaks: drops holds x, y, brightness (Q8) per drop,
    the head at (x, y) and a fading tail above it. p: cols, rows, tail
    length, slant (columns per row, Q8) and color."""
    cols = p[0]
    rows = p[1]
    length = p[2]
    slope = p[3]
    cr = p[4]
    cg = p[5]
    cb = p[6]
    i = 0
    while i < n:
        x = drops[i * 3]
        y = drops[i * 3 + 1]
        k = drops[i * 3 + 2]
        row = y >> 8
        if row < 0:
            row = 0
        last = ((y + length) >> 8) + 1
        if last > rows:
            last = rows
        while row < last:
            u = (row << 8) - y
            w = 0
            if u > -256:
                if u < 0:
                    w = 256 + u
                elif u < length:
                    w = ((length - u) << 8) // length
            if w > 0:
                a = (w * k) >> 8
                _add2(light, cols, row, x + ((slope * u) >> 8),
                      (cr * a) >> 8, (cg * a) >> 8, (cb * a) >> 8)
            row += 1
        i += 1


@micropython.viper
def _points(light: ptr16, pts: ptr32, n: int, p: ptr32):
    """Add soft points: pts holds x, y, brightness (Q8) per point, each
    shared between the four LEDs around it. p: cols, rows, color."""
    cols = p[0]
    rows = p[1]
    cr = p[4]
    cg = p[5]
    cb = p[6]
    i = 0
    while i < n:
        x = pts[i * 3]
        y = pts[i * 3 + 1]
        k = pts[i * 3 + 2]
        row = y >> 8
        up = y & 255
        if row >= 0:
            if row < rows:
                a = (k * (256 - up)) >> 8
                _add2(light, cols, row, x, (cr * a) >> 8, (cg * a) >> 8, (cb * a) >> 8)
        if row + 1 >= 0:
            if row + 1 < rows:
                a = (k * up) >> 8
                _add2(light, cols, row + 1, x, (cr * a) >> 8, (cg * a) >> 8, (cb * a) >> 8)
        i += 1


# Drops, splashes and flakes live in fixed slots of an array('i') and are
# moved here in viper; Python only starts new ones. A slot whose
# brightness (its last entry) is 0 is free. dt16 is the frame time in
# seconds x65536.
DROP = 4                       # x, y, speed (rows/sec), brightness
SPLASH_SLOT = 3                # x, age (ms), brightness
FLAKE = 8                      # x, y, speed, sway, sway phase, sway rate, rested (ms, or -1), brightness


@micropython.viper
def _free(pool: ptr32, slots: int, size: int) -> int:
    """The first free slot, or -1."""
    i = 0
    while i < slots:
        if pool[i * size + size - 1] == 0:
            return i
        i += 1
    return -1


@micropython.viper
def _move_rain(drops: ptr32, slots: int, splashes: ptr32, splash_slots: int,
               out: ptr32, p: ptr32) -> int:
    """Move the drops down and along their slant; a drop that reaches
    the bottom becomes a splash. Writes x, y, brightness for each drop
    still falling to out[] for _streaks and returns how many."""
    cols = p[0]
    slope = p[3]
    dt16 = p[7]
    n = 0
    i = 0
    while i < slots:
        s = i * 4
        k = drops[s + 3]
        if k > 0:
            fall = (drops[s + 2] * dt16) >> 16
            x = drops[s + 0] + ((slope * fall) >> 8)
            y = drops[s + 1] - fall
            drops[s + 0] = x
            drops[s + 1] = y
            if y < 0:
                drops[s + 3] = 0
                if x > -128:
                    if x < (cols << 8) - 128:
                        j = int(_free(splashes, splash_slots, 3))
                        if j >= 0:
                            splashes[j * 3 + 0] = x
                            splashes[j * 3 + 1] = 0
                            splashes[j * 3 + 2] = k
            else:
                out[n * 3 + 0] = x
                out[n * 3 + 1] = y
                out[n * 3 + 2] = k
                n += 1
        i += 1
    return n


@micropython.viper
def _move_splashes(splashes: ptr32, slots: int, out: ptr32, p: ptr32) -> int:
    """Age the splashes: each spreads out to both sides along the bottom
    row as it fades. Writes their points to out[] for _points and
    returns how many."""
    dt_ms = p[8]
    life = p[9]
    bright = p[10]
    n = 0
    i = 0
    while i < slots:
        s = i * 3
        k = splashes[s + 2]
        if k > 0:
            age = splashes[s + 1] + dt_ms
            if age >= life:
                splashes[s + 2] = 0
            else:
                splashes[s + 1] = age
                f = 256 - (age << 8) // life
                a = (((((k * bright) >> 8) * f) >> 8) * f) >> 8
                spread = 77 + ((640 * (256 - f)) >> 8)
                x = splashes[s + 0]
                out[n * 3 + 0] = x - spread
                out[n * 3 + 1] = 0
                out[n * 3 + 2] = a
                out[n * 3 + 3] = x + spread
                out[n * 3 + 4] = 0
                out[n * 3 + 5] = a
                n += 2
        i += 1
    return n


@micropython.viper
def _move_snow(flakes: ptr32, slots: int, sine: ptr16, out: ptr32, p: ptr32) -> int:
    """Move the flakes down, drifting with the wind and swaying; a flake
    that lands rests on the bottom row, fading away. Writes x, y,
    brightness for each to out[] for _points and returns how many."""
    drift = p[2]
    dt16 = p[7]
    dt_ms = p[8]
    settle = p[9]
    n = 0
    i = 0
    while i < slots:
        s = i * 8
        k = flakes[s + 7]
        if k > 0:
            phase = (flakes[s + 4] + ((flakes[s + 5] * dt16) >> 16)) & 65535
            flakes[s + 4] = phase
            sway = (flakes[s + 3] * (int(sine[phase >> 8]) - 256)) >> 8
            x = flakes[s + 0]
            y = flakes[s + 1]
            rested = flakes[s + 6]
            if rested < 0:
                x += (drift * dt16) >> 16
                y -= (flakes[s + 2] * dt16) >> 16
                if y <= 0:
                    # Landed: stays where its sway had it.
                    y = 0
                    x += sway
                    flakes[s + 3] = 0
                    sway = 0
                    rested = 0
                flakes[s + 0] = x
                flakes[s + 1] = y
            else:
                rested += dt_ms
            flakes[s + 6] = rested
            if rested >= settle:
                flakes[s + 7] = 0
            else:
                a = k
                if rested > 0:
                    a = (k * (settle - rested)) // settle
                out[n * 3 + 0] = x + sway
                out[n * 3 + 1] = y
                out[n * 3 + 2] = a
                n += 1
        i += 1
    return n


def _place_stars():
    stars = bytearray(ROWS * COLS)
    spots = [(r, c) for r in range(STAR_LOWEST_ROW, ROWS) for c in range(COLS)]
    for _ in range(STARS):
        r, c = spots.pop(random.randrange(len(spots)))
        stars[r * COLS + c] = random.randint(*STAR_LEVEL)
    return stars


def _spawn_x(travel):
    """Where to start something that will move travel columns sideways
    on its way down, so the whole width gets covered."""
    return random.uniform(min(0.0, -travel) - 0.5, COLS - 0.5 + max(0.0, -travel))


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def live_weather(strips, inbox=None):
    canvas = Canvas(strips)
    light = canvas.light
    if inbox is None:
        inbox = Inbox()
    look = Look()
    stars = _place_stars()
    sky = array.array("H", [0] * (ROWS * 3))
    p = array.array("i", [COLS, ROWS, q8(1 / CLOUD_WIDTH), q8(1 / CLOUD_HEIGHT), 0, 0, 0,
                          q8(1 / CLOUD_EDGE), 0, 0, 0, 0, 0] + to_light(STAR_COLOR) + [q8(CLOUD_SHADE)])
    cloud_at = change_at = twinkle_at = 0.0

    drops = array.array("i", [0] * (RAIN_MOST * DROP))
    splashes = array.array("i", [0] * (RAIN_MOST * SPLASH_SLOT))
    flakes = array.array("i", [0] * (SNOW_MOST * FLAKE))
    points = array.array("i", [0] * (max(RAIN_MOST * 2, SNOW_MOST) * 3))
    sine = array.array("H", [int(256.5 + 256 * math.sin(2 * math.pi * i / 256)) for i in range(256)])
    # cols, rows, streak length or drift, slant, color, dt16, dt (ms),
    # splash or rest time (ms), splash brightness
    rain_p = array.array("i", [COLS, ROWS, q8(RAIN_STREAK), 0, 0, 0, 0, 0, 0,
                               int(SPLASH_S * 1000), q8(SPLASH)])
    snow_p = array.array("i", [COLS, ROWS, 0, 0, 0, 0, 0, 0, 0, int(SNOW_SETTLE_S * 1000)])
    rain_due = snow_due = 0.0
    flash_at = -1.0            # time into a lightning strike, or -1
    last = utime.ticks_ms()

    while True:
        frame_start = utime.ticks_ms()
        dt = min(100, utime.ticks_diff(frame_start, last)) / 1000
        last = frame_start
        for line in inbox.lines():
            got = parse(line)
            if got:
                look.receive(got)
        look.ease(dt)
        wind = look.get("wind")

        # Lightning: a few quick flickers.
        flash = 0.0
        if flash_at >= 0:
            flash_at += dt
            if flash_at > FLASH_S:
                flash_at = -1.0
            else:
                f = flash_at / FLASH_S
                flash = (1 - f) * (0.5 + 0.5 * math.cos(f * 23))
        elif look.get("storm") > 0.5 and random.random() < LIGHTNING_PER_MIN / 60 * dt:
            flash_at = 0.0

        # Sky: the horizon color low down, the top color above.
        for row in range(ROWS):
            f = 1 - row / (ROWS - 1)
            f *= f
            for ch in range(3):
                c = look.get("top", ch) * (1 - f) + look.get("bottom", ch) * f
                sky[row * 3 + ch] = int(LIGHT * (c + (FLASH_COLOR[ch] * 0.3 - c) * flash) + 0.5)

        # Clouds drift with the wind across the mantle.
        speed = CLOUD_DRIFT * wind + (CLOUD_CREEP if wind >= 0 else -CLOUD_CREEP)
        cloud_at = drift(cloud_at, -speed / CLOUD_WIDTH, dt)
        change_at = drift(change_at, CLOUD_CHANGE, dt)
        twinkle_at = drift(twinkle_at, TWINKLE_HZ, dt)
        cover = look.get("cloud")
        p[4] = q8(cloud_at)
        p[5] = q8(change_at)
        # The noise value above which there's cloud: none at 0, all at 1.
        p[6] = int(270.5 - 330 * cover)
        for ch in range(3):
            c = look.get("cloud_color", ch)
            p[8 + ch] = int(LIGHT * (c + (FLASH_COLOR[ch] - c) * flash) + 0.5)
        p[11] = q8(twinkle_at)
        p[12] = int(256 * look.get("stars") + 0.5)
        _sky(light, PERM, p, sky, stars)

        dt_ms = int(dt * 1000 + 0.5)
        dt16 = int(dt * 65536 + 0.5)

        # Rain, slanting with the wind, splashing at the bottom.
        rain = look.get("rain")
        rate = RAIN_PER_MM * rain ** 0.75 if rain > 0.02 else 0.0
        slant = max(-1.2, min(1.2, wind / RAIN_FALL_MS))
        rain_due += rate * dt
        while rain_due >= 1:
            rain_due -= 1
            i = _free(drops, RAIN_MOST, DROP) * DROP
            if i >= 0:
                drops[i] = q8(_spawn_x(slant * (ROWS + 1)))
                drops[i + 1] = q8(ROWS + random.uniform(0, 1))
                drops[i + 2] = q8(random.uniform(*RAIN_SPEED))
                drops[i + 3] = q8(random.uniform(0.5, 1.0))
        rain_p[3] = q8(slant)
        for ch in range(3):
            rain_p[4 + ch] = int(LIGHT * look.get("rain_color", ch) + 0.5)
        rain_p[7] = dt16
        rain_p[8] = dt_ms
        n = _move_rain(drops, RAIN_MOST, splashes, RAIN_MOST, points, rain_p)
        _streaks(light, points, n, rain_p)
        n = _move_splashes(splashes, RAIN_MOST, points, rain_p)
        _points(light, points, n, rain_p)

        # Snow, swaying and drifting with the wind, resting at the bottom.
        snow = look.get("snow")
        rate = SNOW_PER_CM * snow ** 0.7 if snow > 0.01 else 0.0
        drift_x = SNOW_DRIFT * wind
        snow_due += rate * dt
        while snow_due >= 1:
            snow_due -= 1
            i = _free(flakes, SNOW_MOST, FLAKE) * FLAKE
            if i >= 0:
                fall = random.uniform(*SNOW_SPEED)
                flakes[i] = q8(_spawn_x(drift_x * (ROWS + 1) / fall))
                flakes[i + 1] = q8(ROWS + random.uniform(0, 0.5))
                flakes[i + 2] = q8(fall)
                flakes[i + 3] = q8(random.uniform(*SNOW_SWAY))
                flakes[i + 4] = random.randrange(65536)
                flakes[i + 5] = int(65536 * random.uniform(*SNOW_SWAY_HZ))
                flakes[i + 6] = -1
                flakes[i + 7] = 256
        snow_p[2] = q8(drift_x)
        for ch in range(3):
            snow_p[4 + ch] = int(LIGHT * look.get("snow_color", ch) + 0.5)
        snow_p[7] = dt16
        snow_p[8] = dt_ms
        n = _move_snow(flakes, SNOW_MOST, sine, points, snow_p)
        _points(light, points, n, snow_p)

        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
