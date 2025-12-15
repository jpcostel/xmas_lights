
import time
import random
import math
from wiring import *



class Star:
    def __init__(self, strand, index, start_time):
        self.strand = strand
        self.index = index
        self.start = start_time

        # Randomized pulse parameters
        self.duration = random.uniform(0.6, 1.8)     # seconds
        self.min_b = random.uniform(0.15, 0.35)
        self.max_b = random.uniform(0.7, 1.0)

    def alive(self, t):
        return (t - self.start) < self.duration

    def brightness(self, t):
        age = t - self.start
        if age < 0 or age > self.duration:
            return 0.0

        phase = age / self.duration  # 0 → 1
        # Low → high → low cosine envelope
        env = 0.5 * (1 - math.cos(2 * math.pi * phase))
        return self.min_b + (self.max_b - self.min_b) * env

class Ripple:
    def __init__(self, cx, cy, start_time):
        self.cx = cx
        self.cy = cy
        self.start = start_time

        self.speed = random.uniform(6.0, 10.0)   # pixels per second
        self.width = random.uniform(1.5, 3.0)
        self.strength = random.uniform(0.2, 0.5)
        self.max_radius = 30

    def alive(self, t):
        return (t - self.start) * self.speed < self.max_radius

    def brightness_at(self, x, y, t):
        age = t - self.start
        if age < 0:
            return 0.0

        r = age * self.speed
        d = math.hypot(x - self.cx, y - self.cy)

        # Gaussian ring
        return self.strength * math.exp(-((d - r) ** 2) / (2 * self.width ** 2))

stars = []
ripples = []

BACKGROUND_BRIGHTNESS = 0.45
STAR_SPAWN_PROB = 0.7          # ~1 every 1–2 frames @ 60fps
RIPPLE_SPAWN_PROB = 0.002      # rare

t0 = time.time()

color_mask = get_color_mask(strips)

while True:
    now = time.time()
    t = now - t0

    # --- SPAWN STAR ---
    if random.random() < STAR_SPAWN_PROB:
        strand = random.randrange(len(strips))
        index = random.randrange(len(strips[0]))
        stars.append(Star(strand, index, t))

    # --- SPAWN RIPPLE ---
    if random.random() < RIPPLE_SPAWN_PROB:
        cx = random.randrange(25)
        cy = random.randrange(8)
        ripples.append(Ripple(cx, cy, t))

    # --- BACKGROUND ---
    for s in range(len(strips)):
        for i in range(len(strips[s])):
            base = color_mask[s][i]
            strips[s][i] = (
                int(base[0] * BACKGROUND_BRIGHTNESS),
                int(base[1] * BACKGROUND_BRIGHTNESS),
                int(base[2] * BACKGROUND_BRIGHTNESS),
            )

    # --- STARS ---
    stars = [s for s in stars if s.alive(t)]
    for s in stars:
        b = s.brightness(t) ** 2.2
        base = color_mask[s.strand][s.index]
        strips[s.strand][s.index] = (
            int(base[0] * b),
            int(base[1] * b),
            int(base[2] * b),
        )

    # --- RIPPLES ---
    ripples = [r for r in ripples if r.alive(t)]
    for r in ripples:
        for x in range(25):
            for y in range(8):
                add = r.brightness_at(x, y, t)
                if add > 0:
                    strand, index = xy_to_strip(x, y)
                    base = strips[strand][index]
                    strips[strand][index] = (
                        min(255, int(base[0] * (1 + add))),
                        min(255, int(base[1] * (1 + add))),
                        min(255, int(base[2] * (1 + add))),
                    )

    show_all(strips)
    time.sleep(0.016)
