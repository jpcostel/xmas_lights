import math
import random
import utime
from canvas import Canvas
from faces import Eyes
from shapes import Ellipse, Polygon, ease

# ============================================================
# CONFIGURATION
# ============================================================
# Santa, face on: red hat with a white brim and pom-pom, white beard and
# moustache, red nose and rosy cheeks. His eyes blink, look around,
# twinkle and now and then wink, and every so often he laughs, "Ho ho
# ho!", mouth opening and head bouncing with each Ho.
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
TWINKLE = (230, 230, 230)
BEARD = (120, 120, 120)
MOUSTACHE = (200, 200, 200)
MOUTH = (25, 0, 0)
HAT = (170, 0, 0)
FUR = (170, 170, 165)

BEARD_AT = (12.0, 2.3, 5.2, 3.1)          # x, y, half-width, half-height
FACE = (12.0, 3.7, 3.4, 1.35)
EYES = [(10.0, 4.0), (14.0, 4.0)]         # one LED each
EYE_SIZE = (0.6, 0.55)
LOOK_REACH = (0.35, 0.0)
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

# Timing, in seconds.
IDLE_S = (4.0, 8.0)            # between laughs
HO_S = 0.55                    # each Ho...
HOS = 3                        # ...three of them
HO_BOUNCE = 0.35               # rows the head bounces up with each Ho
WINK_CHANCE = 0.3              # chance a pause ends in a wink, not a laugh
WINK_S = 0.6
TWINKLE_EVERY_S = (1.5, 4.0)   # a glint in his eye
TWINKLE_S = 0.35
POM_SPRING_HZ = 2.0            # the pom-pom swings after the head moves
POM_DAMPING = 0.15

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# MOOD
# ============================================================

class Mood:
    """Waiting, laughing (Ho ho ho!) or winking."""

    def __init__(self, t):
        self.what = "idle"
        self.start = t
        self.hold = random.uniform(*IDLE_S)

    def update(self, t):
        """How open the mouth is (0..1), how hard he's laughing (0..1),
        how far the head has bounced up (rows), and how closed the wink
        is (0..1)."""
        age = t - self.start
        if age >= self.hold:
            if self.what == "idle":
                self.what = "wink" if random.random() < WINK_CHANCE else "laugh"
                self.hold = WINK_S if self.what == "wink" else HO_S * HOS
            else:
                self.what = "idle"
                self.hold = random.uniform(*IDLE_S)
            self.start = t
            age = 0.0
        if self.what == "laugh":
            # Each Ho: open quickly, close more slowly.
            f = (age % HO_S) / HO_S
            ho = math.sin(math.pi * min(1.0, f * 1.6))
            joy = math.sin(math.pi * age / self.hold)
            return ho, joy, HO_BOUNCE * ho, 0.0
        if self.what == "wink":
            return 0.0, 0.0, 0.0, math.sin(math.pi * age / self.hold)
        return 0.0, 0.0, 0.0, 0.0


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def santa(strips):
    canvas = Canvas(strips)
    light = canvas.light

    hat = Polygon(HAT)
    hat_tip = Polygon(HAT, sides=3)
    beard = Ellipse(BEARD)
    face = Ellipse(SKIN)
    cheeks = [Ellipse(CHEEKS) for _ in CHEEK_AT]
    eye_shapes = [Ellipse(EYE, soft=CRISP) for _ in EYES]
    twinkle = Ellipse(TWINKLE, soft=CRISP)
    nose = Ellipse(NOSE, soft=CRISP)
    moustache = [Ellipse(MOUSTACHE, soft=CRISP) for _ in MOUSTACHE_AT]
    mouth = Ellipse(MOUTH, soft=CRISP)
    brim = Ellipse(FUR)
    pom = Ellipse(FUR)

    scene_start = utime.ticks_ms()
    eyes = Eyes(0.0)
    mood = Mood(0.0)
    twinkle_at = random.uniform(*TWINKLE_EVERY_S)
    twinkle_eye = 0
    pom_y = pom_v = 0.0
    stiffness = (2 * math.pi * POM_SPRING_HZ) ** 2
    damping = 2 * POM_DAMPING * math.sqrt(stiffness)
    last_t = 0.0

    while True:
        frame_start = utime.ticks_ms()
        t = utime.ticks_diff(frame_start, scene_start) / 1000
        dt = min(0.1, t - last_t)
        last_t = t

        opened, look_x, look_y = eyes.update(t)
        ho, joy, dy, wink = mood.update(t)
        # Eyes crinkle shut with laughter.
        opened = min(opened, 1.0 - 0.8 * ho)

        pom_v += (stiffness * (dy - pom_y) - damping * pom_v) * dt
        pom_y += pom_v * dt

        hat.set([(px, py + dy) for px, py in HAT_BODY])
        hat_tip.set([(px, py + dy + (pom_y - dy) * (px - 15.6) / 5.7) for px, py in HAT_TIP])
        x, y, rx, ry = BEARD_AT
        beard.set(x, y + dy * 0.5, rx, ry)
        x, y, rx, ry = FACE
        face.set(x, y + dy, rx, ry)
        for cheek, (cx, cy) in zip(cheeks, CHEEK_AT):
            cheek.set(cx, cy + dy, CHEEK_R, CHEEK_R * 0.7, CHEEK_ALPHA * (1 + joy))
        for i, (ex, ey) in enumerate(EYES):
            shut = opened if i == 0 else min(opened, 1.0 - wink)
            eye_shapes[i].set(ex + LOOK_REACH[0] * look_x, ey + dy, EYE_SIZE[0],
                              EYE_SIZE[1] * max(0.25, shut), 0.6 + 0.4 * shut)
        # Now and then a twinkle in one eye.
        g = t - twinkle_at
        if g >= TWINKLE_S:
            twinkle_at = t + random.uniform(*TWINKLE_EVERY_S)
            twinkle_eye = random.randrange(2)
        sparkle = math.sin(math.pi * g / TWINKLE_S) if g >= 0.0 else 0.0
        ex, ey = EYES[twinkle_eye]
        twinkle.set(ex + LOOK_REACH[0] * look_x, ey + dy, 0.4, 0.4, 0.8 * sparkle * opened)
        nose.set(NOSE_AT[0], NOSE_AT[1] + dy, NOSE_AT[2], NOSE_AT[2] * 0.8)
        mx, my, mw = MOUTH_AT
        mouth.set(mx, my + dy * 0.5 - 0.2 * ho, mw + 0.4 * ho, 0.3 + 0.5 * ho, 0.5 + 0.5 * ease(ho * 2))
        for m, (x, y, rx, ry) in zip(moustache, MOUSTACHE_AT):
            m.set(x, y + dy * 0.8, rx, ry)
        brim.set(BRIM_AT[0], BRIM_AT[1] + dy, BRIM_AT[2], BRIM_AT[3])
        pom.set(POM_AT[0], POM_AT[1] + pom_y, POM_AT[2], POM_AT[2])

        canvas.clear()
        for shape in (hat, hat_tip, beard, face, cheeks[0], cheeks[1], eye_shapes[0], eye_shapes[1],
                      twinkle, nose, mouth, moustache[0], moustache[1], brim, pom):
            shape.draw(light)
        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
