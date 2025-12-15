import math
import random
import utime
from wiring import *
from grid import grid_to_pixel as xy_to_strip

# ============================================================
# CONFIGURATION
# ============================================================

GRID_WIDTH = 25
GRID_HEIGHT = 8

BACKGROUND_BRIGHTNESS = 0.33

STAR_SPAWN_PROB = 0.8      # per frame (~1 every 1–2 frames)
RIPPLE_SPAWN_PROB = 0.005  # rare event

# FRAME_MS = 16              # ~60 FPS
FRAME_MS = 33              # ~30 FPS


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

    def alive(self, now_ms):
        return utime.ticks_diff(now_ms, self.start_ms) < self.duration_ms

    def brightness(self, now_ms):
        age = utime.ticks_diff(now_ms, self.start_ms)
        if age < 0 or age > self.duration_ms:
            return 0.0

        phase = age / self.duration_ms  # 0 → 1

        # Low → high → low cosine envelope
        env = 0.5 * (1 - math.cos(2 * math.pi * phase))
        return self.min_b + (self.max_b - self.min_b) * env


# ============================================================
# RIPPLE OBJECT (brightness-only expanding wave)
# ============================================================

class Ripple:
    def __init__(self, cx, cy, start_ms):
        self.cx = cx
        self.cy = cy
        self.start_ms = start_ms

        self.speed = random.uniform(18.0, 25.0)   # pixels/sec
        self.width = random.uniform(1.0, 2.0)
        self.strength = random.uniform(0.6, 0.9)
        self.max_radius = 30

    def alive(self, now_ms):
        age_ms = utime.ticks_diff(now_ms, self.start_ms)
        return (age_ms * self.speed / 1000) < self.max_radius

    def brightness_at(self, x, y, now_ms):
        age_ms = utime.ticks_diff(now_ms, self.start_ms)
        if age_ms < 0:
            return 0.0

        r = (age_ms / 1000) * self.speed
        d = math.sqrt((x - self.cx)**2 + (y - self.cy)**2)

        # Gaussian ring
        return self.strength * math.exp(-((d - r)**2) / (2 * self.width**2))


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def starfield(strips, ripples_on=True):

    color_mask = get_color_mask(strips)

    stars = []
    ripples = []

    last_frame_ms = utime.ticks_ms()

    while True:
        frame_start = utime.ticks_ms()

        # ----------------------------------------------------
        # SPAWN NEW STAR
        # ----------------------------------------------------
        if random.random() < STAR_SPAWN_PROB:
            strand = random.randrange(len(strips))
            index = random.randrange(len(strips[0]))
            stars.append(Star(strand, index, frame_start))

        # ----------------------------------------------------
        # SPAWN RIPPLE (RARE)
        # ----------------------------------------------------
        if ripples_on:
            if random.random() < RIPPLE_SPAWN_PROB:
                cx = random.randrange(GRID_WIDTH)
                cy = random.randrange(GRID_HEIGHT)
                ripples.append(Ripple(cx, cy, frame_start))

        # ----------------------------------------------------
        # BACKGROUND DRAW
        # ----------------------------------------------------
        for s in range(len(strips)):
            strip = strips[s]
            mask = color_mask[s]
            for i in range(len(strip)):
                strip[i] = (
                    int(mask[i][0] * BACKGROUND_BRIGHTNESS),
                    int(mask[i][1] * BACKGROUND_BRIGHTNESS),
                    int(mask[i][2] * BACKGROUND_BRIGHTNESS),
                )

        # ----------------------------------------------------
        # STARS
        # ----------------------------------------------------
        new_stars = []
        for star in stars:
            if not star.alive(frame_start):
                continue

            b = star.brightness(frame_start)
            b = b * b  # simple gamma-ish correction

            base = color_mask[star.strand][star.index]
            strips[star.strand][star.index] = (
                int(base[0] * b),
                int(base[1] * b),
                int(base[2] * b),
            )

            new_stars.append(star)
        stars = new_stars

        # ----------------------------------------------------
        # RIPPLES
        # ----------------------------------------------------
        new_ripples = []
        if ripples_on:
            for ripple in ripples:
                if not ripple.alive(frame_start):
                    continue

                for x in range(GRID_WIDTH):
                    for y in range(GRID_HEIGHT):
                        add = ripple.brightness_at(x, y, frame_start)
                        if add <= 0:
                            continue

                        strand, index = xy_to_strip(y, x)
                        r, g, b = strips[strand][index]

                        scale = 1.0 + add
                        strips[strand][index] = (
                            min(255, int(r * scale)),
                            min(255, int(g * scale)),
                            min(255, int(b * scale)),
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
