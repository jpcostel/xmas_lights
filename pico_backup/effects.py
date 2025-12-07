import time
import math
import random
import wiring



# -------------------------
# HARDWARE CONFIG
# -------------------------

strips = wiring.strips
PIXELS_PER_STRAND = wiring.PIXELS_PER_STRAND
NUM_STRANDS = wiring.NUM_STRANDS


# -------------------------
# UTILITY FUNCTIONS
# -------------------------

all_pixels = wiring.all_pixels
show_all = wiring.show_all
clear = wiring.clear
get_color_mask = wiring.get_color_mask


# -------------------------
# 1. GLOBAL BREATHING / COLOR-CYCLING PULSE
# -------------------------

def pulse_all(strips, cycle_time=4.0):
    """
    Slowly pulse ALL LEDs together.
    
    At the dimmest point of the pulse cycle, change the color.

    cycle_time: seconds per full bright→dim→bright cycle
    """
    hue = 0.0  # start color (0 = red)
    cycle_ms = cycle_time * 1000

    while True:
        start = time.ticks_ms()

        # use a sinusoidal breathing curve
        while True:
            now = time.ticks_ms()
            elapsed = time.ticks_diff(now, start)
            
            t = elapsed / cycle_ms
            if t >= 1.0:
                break

            # brightness 0..1
            brightness = 0.5 * (1 - math.cos(2 * math.pi * t))

            # at brightness near zero → change color
            if brightness < 0.02:
                hue = (hue + 0.08) % 1.0   # slowly rotate through spectrum

            # convert hue to RGB
            r, g, b = hsv_to_rgb(hue, 1.0, brightness)

            all_pixels(strips, (int(r), int(g), int(b)))
            show_all(strips)
            time.sleep_ms(10)



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

def get_stars(num_stars):
    stars = []
    for _ in range(num_stars):
        strand = random.randrange(len(strips))
        index = random.randrange(len(strips[0]))
        phase = random.random() * 2 * math.pi
        speed = random.uniform(1.0, 3.0)
        stars.append((strand, index, phase, speed))
    return stars


def twinkle_stars(strips, num_stars=25):
    # 1. GENERATE THE PERMANENT COLOR MAP
    # We do this once. These colors will never change, only their brightness will.
    color_mask = get_color_mask(strips)
    for strip in range(len(strips)):
        for pix in range(len(strips[strip])):
            strips[strip][pix] = color_mask[strip][pix]

    # 2. SETUP STARS
    # We track stars by (strand, index, phase, speed)
    stars = get_stars(num_stars)
    
    t0 = time.ticks_ms()

    while True:
        
        loop_start = time.ticks_ms()
        t = time.ticks_diff(loop_start, t0) / 1000

        # --- OPTIMIZATION: DRAWING STRATEGY ---
        # Instead of 'colorize' looping over every pixel every frame (slow!),
        # we only loop over the stars.
        
        # 1. Clear previous stars (optional) or Draw Background
        # If you want a dim background, set it here. If you want black background:
        # all_pixels(strips, (0,0,0)) 
        
        # 2. Update and Draw Stars
        
        for strand, index, phase, speed in stars:
            
            # Calculate brightness (0.0 to 1.0)
            raw = 0.5 * (1 - math.cos(speed * t + phase))
            # Add a brightness floor
            min_brightness = 0.25
            raw = min_brightness + (1 - min_brightness) * raw
            
            b = raw ** 2.2 # Gamma correction for nicer fade

            # Retrieve the correct color from our "Source of Truth"
            # We don't read the strip, we read the mask.
            base_color = color_mask[strand][index]
            
            # Apply brightness to that color
#             final_color = (
#                 int(base_color[0] * b),
#                 int(base_color[1] * b),
#                 int(base_color[2] * b)
#             )
            final_color = (
            max(10, int(base_color[0] * b)) if base_color[0] > 0 and b > 0 else 0,
            max(10, int(base_color[1] * b)) if base_color[1] > 0 and b > 0 else 0,
            max(10, int(base_color[2] * b)) if base_color[2] > 0 and b > 0 else 0
            )
            # Write to strip
            
            strips[strand][index] = final_color
            # print("Strand: {}\t\tIndex:{}\t\tFinal Color:{}".format(strand, index, final_color))

        show_all(strips)
        loop_end = time.ticks_ms()
        # print("Loop Time: {}".format(time.ticks_diff(loop_end, loop_start)))
        time.sleep_ms(16 - time.ticks_diff(loop_start,loop_end))
        # EVERY 5 SECONDS
        if (loop_end - t0) > 5000:
                # REINITTIALIZE ALL LIGHTS
                for strip in range(len(strips)):
                    for pix in range(len(strips[strip])):
                        strips[strip][pix] = color_mask[strip][pix]

                # RANDOMIZE NEW STARS
                stars = get_stars(num_stars)
                
                # RESTART THE SECOND TIMER
                t0 = time.ticks_ms()


# -------------------------
# Move lights along each string 
# -------------------------
def blink(strips, gap=2, offset=0, color=(0,0,255), sleep=0.1):
    ci = ((255,255,0), (0,0,255), (255,0,0), (0,255,0), (0,255,255), (255,0,255))
    gap = gap + 1
    for strip in strips:
        strip.fill((0,0,0))
        for i in range(strip.n):
            index = i % 6
            color = ci[index]
            if (i+offset) % gap == 0:
                strip[i] = color
    show_all(strips)


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
