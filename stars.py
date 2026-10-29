import math
import micropython
import random
import utime
from wiring import *
from grid import grid_to_pixel as xy_to_strip

# ============================================================
# CONFIGURATION
# ============================================================

GRID_WIDTH = 25
GRID_HEIGHT = 8

BACKGROUND_BRIGHTNESS = 0.25

# Spawn rates are per second so the sky looks the same at any frame rate
# (they match the old per-frame chances at the ~25 FPS this ran at).
STARS_PER_SEC = 37.5
RIPPLES_PER_SEC = 0.375    # rare event
RIPPLE_REACH = 3.5         # ring widths beyond which a ripple changes nothing

FRAME_MS = 16              # ~60 FPS
# FRAME_MS = 33              # ~30 FPS


# ============================================================
# HELPERS YOU ALREADY HAVE
# ============================================================
# Assumed to exist in your codebase:
#
# strips              -> list of NeoPixel strips
# color_mask          -> immutable base color per pixel
# show_all(strips)
# xy_to_strip(x, y)   -> maps grid coords to (strand, index)
#
# ============================================================

# ============================================================
# STAR OBJECT (single pulse, finite lifetime)
# ============================================================

class Star:
    def __init__(self, strand, index, start_ms):
        self.strand = strand
        self.index = index
        self.start_ms = start_ms

        # Randomized pulse parameters
        self.duration_ms = random.randint(600, 3600)
        self.min_b = random.uniform(0.15, 0.35)
        self.max_b = random.uniform(0.7, 1.0)



@micropython.native
def _draw_stars(stars, now_ms, color_mask, pixels):
    """Draw every live star; returns the stars still alive.

    One compiled pass instead of two Python method calls per star per
    frame, which was most of this scene's frame time.
    """
    alive = []
    two_pi = 2 * math.pi
    for star in stars:
        age = utime.ticks_diff(now_ms, star.start_ms)
        if age >= star.duration_ms:
            continue
        b = 0.0
        if age >= 0:
            phase = age / star.duration_ms  # 0 → 1
            # Low → high → low cosine envelope
            env = 0.5 * (1 - math.cos(two_pi * phase))
            b = star.min_b + (star.max_b - star.min_b) * env
        b = b * b  # simple gamma-ish correction

        base = color_mask[star.strand][star.index]
        buf, ro, go, bo = pixels[star.strand][star.index]
        buf[ro] = int(base[0] * b)
        buf[go] = int(base[1] * b)
        buf[bo] = int(base[2] * b)
        alive.append(star)
    return alive


# ============================================================
# RIPPLE OBJECT (brightness-only expanding wave)
# ============================================================

class Ripple:
    def __init__(self, cx, cy, start_ms, pixels):
        self.cx = cx
        self.cy = cy
        self.start_ms = start_ms

        self.speed = random.uniform(9.0, 12.0)   # pixels/sec
        self.width = random.uniform(1.0, 2.0)
        self.strength = random.uniform(0.6, 0.9)
        self.max_radius = 30

        # Each pixel's distance from the center never changes, so work it
        # out once instead of a sqrt per pixel per frame.
        self.cells = []
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                d = math.sqrt((x - cx)**2 + (y - cy)**2)
                strand, index = xy_to_strip(y, x)
                self.cells.append((d,) + pixels[strand][index])
        self.reach = RIPPLE_REACH * self.width
        self.last_d = max(c[0] for c in self.cells)

    def radius(self, now_ms):
        return (utime.ticks_diff(now_ms, self.start_ms) / 1000) * self.speed

    def alive(self, now_ms):
        r = self.radius(now_ms)
        # Done once the ring is past the farthest pixel it could still brighten.
        return r < self.max_radius and r - self.reach < self.last_d


@micropython.native
def _apply_ripple(cells, r, reach, inv_2w2, strength):
    """Brighten the pixels near a ripple's ring (a Gaussian in distance).

    Pixels more than `reach` from the ring would change by under one
    brightness step, so they're skipped rather than run through exp().
    """
    for d, buf, ro, go, bo in cells:
        x = d - r
        if x > reach or x < -reach:
            continue
        scale = 1.0 + strength * math.exp(-x * x * inv_2w2)
        v = int(buf[ro] * scale)
        buf[ro] = v if v < 255 else 255
        v = int(buf[go] * scale)
        buf[go] = v if v < 255 else 255
        v = int(buf[bo] * scale)
        buf[bo] = v if v < 255 else 255


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def starfield(strips, ripples_on=True, pallet=0):

    color_mask = get_color_mask(strips, pallet=pallet)
    pixels = strand_map(strips)

    # The dimmed palette background never changes: draw it once and copy
    # the bytes back at the start of each frame.
    for s in range(len(strips)):
        mask = color_mask[s]
        for i in range(len(strips[s])):
            buf, ro, go, bo = pixels[s][i]
            buf[ro] = int(mask[i][0] * BACKGROUND_BRIGHTNESS)
            buf[go] = int(mask[i][1] * BACKGROUND_BRIGHTNESS)
            buf[bo] = int(mask[i][2] * BACKGROUND_BRIGHTNESS)
    background = snapshot(strips)

    stars = []
    ripples = []

    last_frame_ms = utime.ticks_ms()

    while True:
        frame_start = utime.ticks_ms()
        dt = utime.ticks_diff(frame_start, last_frame_ms) / 1000
        last_frame_ms = frame_start

        # ----------------------------------------------------
        # SPAWN NEW STARS
        # ----------------------------------------------------
        # Whole stars owed for this frame, plus a chance at one more for
        # the fraction left over.
        due = STARS_PER_SEC * dt
        while due >= 1 or random.random() < due:
            strand = random.randrange(len(strips))
            index = random.randrange(len(strips[0]))
            stars.append(Star(strand, index, frame_start))
            due -= 1

        # ----------------------------------------------------
        # SPAWN RIPPLE (RARE)
        # ----------------------------------------------------
        if ripples_on:
            if random.random() < RIPPLES_PER_SEC * dt:
                cx = random.randrange(GRID_WIDTH)
                cy = random.randrange(GRID_HEIGHT)
                ripples.append(Ripple(cx, cy, frame_start, pixels))

        # ----------------------------------------------------
        # BACKGROUND DRAW
        # ----------------------------------------------------
        restore(strips, background)

        # ----------------------------------------------------
        # STARS
        # ----------------------------------------------------
        stars = _draw_stars(stars, frame_start, color_mask, pixels)

        # ----------------------------------------------------
        # RIPPLES
        # ----------------------------------------------------
        new_ripples = []
        if ripples_on:
            for ripple in ripples:
                if not ripple.alive(frame_start):
                    continue
                _apply_ripple(
                    ripple.cells,
                    ripple.radius(frame_start),
                    ripple.reach,
                    1 / (2 * ripple.width ** 2),
                    ripple.strength,
                )
                new_ripples.append(ripple)
        ripples = new_ripples

        # ----------------------------------------------------
        # SHOW + FRAME TIMING
        # ----------------------------------------------------
        show_all(strips)

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
