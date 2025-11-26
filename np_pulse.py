import time
import math
import random
import board
import neopixel

# -------------------------
# HARDWARE CONFIG
# -------------------------

PIXELS_PER_STRAND = 100
NUM_STRANDS = 2

DATA_PINS = [
    board.D18,   # Strand 0
    board.D19,   # Strand 1
]

# Initialize strips
strips = [
    neopixel.NeoPixel(
        DATA_PINS[i],
        PIXELS_PER_STRAND,
        auto_write=False,
        pixel_order=neopixel.GRB
    )
    for i in range(NUM_STRANDS)
]


# -------------------------
# UTILITY FUNCTIONS
# -------------------------

def all_pixels(color):
    """Set every pixel on every strand."""
    for strip in strips:
        strip.fill(color)


def show_all():
    """Push updates to all strips."""
    for strip in strips:
        strip.show()


def clear():
    all_pixels((0,0,0))
    show_all()


# -------------------------
# 1. GLOBAL BREATHING / COLOR-CYCLING PULSE
# -------------------------

def pulse_all(cycle_time=4.0):
    """
    Slowly pulse ALL LEDs together.
    
    At the dimmest point of the pulse cycle, change the color.

    cycle_time: seconds per full bright→dim→bright cycle
    """
    hue = 0.0  # start color (0 = red)

    while True:
        start = time.time()

        # use a sinusoidal breathing curve
        while True:
            t = (time.time() - start) / cycle_time
            if t >= 1.0:
                break

            # brightness 0..1
            brightness = 0.5 * (1 - math.cos(2 * math.pi * t))

            # at brightness near zero → change color
            if brightness < 0.02:
                hue = (hue + 0.08) % 1.0   # slowly rotate through spectrum

            # convert hue to RGB
            r, g, b = hsv_to_rgb(hue, 1.0, brightness)

            all_pixels((int(r), int(g), int(b)))
            show_all()
            time.sleep(0.01)


# -------------------------
# 2. RANDOM TWINKLING STARS
# -------------------------

class Star:
    def __init__(self, strand, index):
        self.strand = strand
        self.index = index
        self.offset = random.random() * 2 * math.pi  # random phase start
        self.speed = random.uniform(1.0, 3.5)        # each star pulses differently

    def brightness(self, t):
        return 0.5 * (1 - math.cos(self.speed * t + self.offset))

    def color(self, t):
        b = self.brightness(t)
        return (int(255*b), int(255*b), int(255*b))  # white twinkles


def twinkle_stars(num_stars=25):
    """
    Smooth, independent twinkling stars with no flicker or stutter.
    Uses gamma-corrected sinusoidal brightness for natural sparkle.
    """

    # pick random LED coordinates
    stars = []
    for _ in range(num_stars):
        strand = random.randrange(NUM_STRANDS)
        index = random.randrange(PIXELS_PER_STRAND)
        phase = random.random() * 2 * math.pi
        speed = random.uniform(0.5, 2.0)  # slower = smoother and more elegant
        stars.append((strand, index, phase, speed))

    t0 = time.time()

    # keep background off unless you want a color
    all_pixels((0, 0, 0))

    while True:
        t = time.time() - t0

        # no more clearing — overwrite only the star LEDs
        for strand, pixel, phase, speed in stars:

            # smooth brightness 0–1
            raw = 0.5 * (1 - math.cos(speed * t + phase))

            # gamma correction
            b = raw ** 2.2

            val = int(255 * b)
            strips[strand][pixel] = (val, val, (val/255)*16)

        show_all()
        time.sleep(0.01)  # smooth 100 FPS update



# -------------------------
# HELPER: HSV → RGB conversion
# -------------------------

def hsv_to_rgb(h, s, v):
    """Simple float HSV to integer RGB."""
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    i = i % 6

    if i == 0: r, g, b = v, t, p
    elif i == 1: r, g, b = q, v, p
    elif i == 2: r, g, b = p, v, t
    elif i == 3: r, g, b = p, q, v
    elif i == 4: r, g, b = t, p, v
    elif i == 5: r, g, b = v, p, q

    return int(r*255), int(g*255), int(b*255)
