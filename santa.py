import array
import math
import random
import utime
from canvas import Canvas
from faces import Eyes
from shapes import Ellipse, Polygon

# ============================================================
# CONFIGURATION
# ============================================================
# Santa, face on: red hat with a white brim and pom-pom, white beard and
# moustache, red nose and rosy cheeks. His eyes blink, look from side
# to side and now and then wink.
#
# Positions are in LED spacings: x = column, y = row (0 = bottom).
# Colors are as they'd look with gamma off. At 8 rows each feature
# gets its own rows, lined up on the LEDs: hat 6-7, brim 5, eyes 4,
# nose and cheeks 3, moustache 2, beard 0-1.

SKIN = (130, 58, 28)
NOSE = (210, 25, 15)
CHEEKS = (210, 30, 30)
CHEEK_ALPHA = 0.45
EYE = (0, 0, 0)
BEARD = (120, 120, 120)
MOUSTACHE = (200, 200, 200)
MOUTH = (25, 0, 0)
HAT = (170, 0, 0)
FUR = (170, 170, 165)

BEARD_AT = (12.0, 2.3, 5.2, 3.1)          # x, y, half-width, half-height
FACE = (12.0, 3.7, 3.4, 1.35)
EYES = [(10.5, 4.0), (13.5, 4.0)]         # two LEDs each
EYE_SIZE = (1.05, 0.55)
LOOK_REACH = (1.0, 0.0)                   # a whole LED, so the move is clear...
LOOKS = [(0.0, 0.0), (0.0, 0.0), (-1.0, 0.0), (1.0, 0.0)]   # ...ending on the LEDs
NOSE_AT = (12.0, 3.0, 0.6)
CHEEK_AT = [(9.6, 3.0), (14.4, 3.0)]
CHEEK_R = 0.8
MOUSTACHE_AT = [(10.4, 2.1, 1.9, 0.6), (13.6, 2.1, 1.9, 0.6)]
MOUTH_AT = (12.0, 1.0, 0.9)               # x, y, half-width
HAT_BODY = [(7.0, 5.6), (17.0, 5.6), (17.8, 7.3), (11.0, 8.0)]
HAT_TIP = [(15.6, 7.8), (18.0, 6.4), (21.3, 6.3)]
BRIM_AT = (12.0, 5.05, 5.4, 0.55)
POM_AT = (21.6, 6.5, 0.9)
CRISP = 0.45                              # edge softness of the small features

# Timing, in seconds. One-row eyes blink better slow and seldom: quick
# ones look like a flicker.
BLINK_EVERY_S = (3.0, 7.0)
BLINK_S = 0.28
WINK_EVERY_S = (8.0, 20.0)
WINK_S = 0.6

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def santa(strips):
    canvas = Canvas(strips)
    light = canvas.light

    # Everything but the eyes stays still: paint it once and copy it in
    # each frame.
    still = [Polygon(HAT, HAT_BODY), Polygon(HAT, HAT_TIP, sides=3),
             Ellipse(BEARD, *BEARD_AT), Ellipse(SKIN, *FACE)]
    still += [Ellipse(CHEEKS, x, y, CHEEK_R, CHEEK_R * 0.7, CHEEK_ALPHA) for x, y in CHEEK_AT]
    still.append(Ellipse(NOSE, NOSE_AT[0], NOSE_AT[1], NOSE_AT[2], NOSE_AT[2] * 0.8, soft=CRISP))
    mx, my, mw = MOUTH_AT
    still.append(Ellipse(MOUTH, mx, my, mw, 0.3, 0.5, soft=CRISP))
    still += [Ellipse(MOUSTACHE, *m, soft=CRISP) for m in MOUSTACHE_AT]
    still.append(Ellipse(FUR, *BRIM_AT))
    still.append(Ellipse(FUR, POM_AT[0], POM_AT[1], POM_AT[2], POM_AT[2]))
    for shape in still:
        shape.draw(light)
    face = array.array("H", light)

    eye_shapes = [Ellipse(EYE, soft=CRISP) for _ in EYES]
    scene_start = utime.ticks_ms()
    eyes = Eyes(0.0, BLINK_EVERY_S, BLINK_S, 0.0, LOOKS)
    wink_at = random.uniform(*WINK_EVERY_S)

    while True:
        frame_start = utime.ticks_ms()
        t = utime.ticks_diff(frame_start, scene_start) / 1000

        opened, look_x, look_y = eyes.update(t)
        g = t - wink_at
        wink = 0.0
        if g >= WINK_S:
            wink_at = t + random.uniform(*WINK_EVERY_S)
        elif g >= 0.0:
            wink = math.sin(math.pi * g / WINK_S)

        light[:] = face
        x = LOOK_REACH[0] * look_x
        for i, (ex, ey) in enumerate(EYES):
            shut = opened if i == 0 else min(opened, 1.0 - wink)
            eye_shapes[i].set(ex + x, ey, EYE_SIZE[0], EYE_SIZE[1] * max(0.25, shut), 0.6 + 0.4 * shut)
            eye_shapes[i].draw(light)
        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
