"""Life for cartoon faces: eyes that blink and look around."""
import math
import random
from shapes import ease

BLINK_EVERY_S = (2.0, 5.5)
BLINK_S = 0.18
DOUBLE_BLINK = 0.25            # chance a blink comes in a pair
LOOK_EVERY_S = (1.2, 3.5)
LOOK_S = 0.25                  # time to move the eyes to a new spot
# Where the eyes look, as fractions of how far they can move: mostly
# ahead, sometimes to a side or up.
LOOKS = [(0.0, 0.0), (0.0, 0.0), (-1.0, 0.0), (1.0, 0.0), (-0.7, 0.5), (0.7, 0.5), (0.0, -0.5)]


class Eyes:
    def __init__(self, t, blink_every=BLINK_EVERY_S, blink_s=BLINK_S, double_blink=DOUBLE_BLINK,
                 looks=LOOKS):
        self.looks = looks
        self.blink_every = blink_every
        self.blink_s = blink_s
        self.double_blink = double_blink
        self.blink_at = t + random.uniform(*blink_every)
        self.look_at = t + random.uniform(*LOOK_EVERY_S)
        self.look_start = t
        self.look_from = (0.0, 0.0)
        self.look_to = (0.0, 0.0)

    def update(self, t):
        """How open the eyes are (0..1), and where they're looking
        (dx, dy, each -1..1)."""
        g = t - self.blink_at
        opened = 1.0
        if g >= self.blink_s:
            if random.random() < self.double_blink:
                self.blink_at = t + 0.12
            else:
                self.blink_at = t + random.uniform(*self.blink_every)
        elif g >= 0.0:
            opened = 1.0 - math.sin(math.pi * g / self.blink_s)

        if t >= self.look_at:
            self.look_from = self.where(t)
            self.look_to = random.choice(self.looks)
            self.look_start = t
            self.look_at = t + LOOK_S + random.uniform(*LOOK_EVERY_S)
        dx, dy = self.where(t)
        return opened, dx, dy

    def where(self, t):
        f = ease((t - self.look_start) / LOOK_S)
        (x0, y0), (x1, y1) = self.look_from, self.look_to
        return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
