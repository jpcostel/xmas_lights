import math
import random
import utime
from canvas import Canvas
from faces import Eyes
from shapes import Ellipse, Polygon, ease

# ============================================================
# CONFIGURATION
# ============================================================
# One of Santa's elves, face on: pointy ears, a floppy hat with a
# pom-pom, rosy cheeks. The eyes blink and look around, and every few
# seconds the elf chats or giggles, ears wiggling and pom-pom bouncing.
#
# Positions are in LED spacings: x = column, y = row (0 = bottom).
# Colors are as they'd look with gamma off.

SKIN = (130, 58, 28)
NOSE = (170, 55, 30)
INNER_EAR = (70, 22, 10)
CHEEKS = (200, 30, 30)
CHEEK_ALPHA = 0.5
EYE = (0, 0, 0)
GLINT = (200, 200, 200)
MOUTH = (0, 0, 0)
TONGUE = (150, 10, 10)
HAT = (0, 120, 15)
BRIM = (170, 0, 0)
POM_POM = (170, 170, 160)

# At 8 rows each feature gets its own rows, lined up on the LEDs, so it
# reads crisply: hat 6-7, brim 5, eyes 3-4, nose and cheeks 2, smile 1.
FACE = (12.0, 2.5, 4.3, 2.75)              # x, y, half-width, half-height
# Each ear: where it meets the face (top, bottom), its lower edge, its tip.
EARS = [((8.6, 4.6), (8.6, 2.2), (6.2, 3.2), (4.6, 5.4)),
        ((15.4, 4.6), (15.4, 2.2), (17.8, 3.2), (19.4, 5.4))]
INNER_EARS = [((8.2, 4.2), (8.2, 3.1), (6.7, 3.7), (5.6, 5.0)),
              ((15.8, 4.2), (15.8, 3.1), (17.3, 3.7), (18.4, 5.0))]
EYES = [(10.5, 3.5), (13.5, 3.5)]         # each a 2x2 block of LEDs
EYE_SIZE = (1.05, 1.1)
GLINT_AT = (-0.5, 0.5, 0.35, 0.55)         # glint offset in the eye, size, brightness
LOOK_REACH = (0.35, 0.2)                   # how far the eyes move
NOSE_AT = (12.0, 2.1, 0.55)
CHEEK_AT = [(9.3, 2.0), (14.7, 2.0)]
CHEEK_R = 0.7
SMILE_AT = (12.0, 1.0, 2.4)                # middle and half-width of the smile...
CORNERS_DX = 3.0                           # ...its corners, turned up a row
CORNER_R = 0.5
CRISP = 0.45                               # edge softness of the small features
HAT_BODY = [(8.0, 5.6), (16.0, 5.6), (17.0, 7.3), (11.0, 7.9)]
HAT_TIP = [(15.0, 7.8), (17.2, 6.3), (21.3, 6.3)]
BRIM_AT = (12.0, 5.0, 3.9, 0.5)
POM_AT = (21.6, 6.5, 0.9)

# Timing, in seconds.
IDLE_S = (2.5, 6.0)            # just smiling between chats and giggles
CHAT_S = (1.5, 2.8)
CHAT_HZ = 4.0                  # mouth opening and closing
GIGGLE_S = 1.6
GIGGLE_HZ = 5.0                # little bounces
GIGGLE_BOUNCE = 0.3            # rows
EAR_WIGGLE = 0.4               # rows the ear tips flick while giggling
POM_SPRING_HZ = 2.0            # the pom-pom swings after the head moves
POM_DAMPING = 0.15

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# MOOD
# ============================================================

class Mood:
    """Smiling, chatting or giggling, in turns."""

    def __init__(self, t):
        self.what = "idle"
        self.start = t
        self.hold = random.uniform(*IDLE_S)

    def update(self, t):
        """How open the mouth is (0..1), how hard it's giggling (0..1)
        and how far the head has bounced up (rows)."""
        age = t - self.start
        if age >= self.hold:
            if self.what == "idle":
                self.what = random.choice(("chat", "chat", "giggle"))
                self.hold = random.uniform(*CHAT_S) if self.what == "chat" else GIGGLE_S
            else:
                self.what = "idle"
                self.hold = random.uniform(*IDLE_S)
            self.start = t
            age = 0.0
        if self.what == "chat":
            # Fades in and out over the first and last bit.
            env = min(1.0, age / 0.2, (self.hold - age) / 0.2)
            return env * (0.5 - 0.5 * math.cos(2 * math.pi * CHAT_HZ * age)), 0.0, 0.0
        if self.what == "giggle":
            env = math.sin(math.pi * age / self.hold)
            bounce = GIGGLE_BOUNCE * env * abs(math.sin(math.pi * GIGGLE_HZ * age))
            return 0.8 * ease(min(1.0, age / 0.15, (self.hold - age) / 0.15)), env, bounce
        return 0.0, 0.0, 0.0


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def santas_elf(strips):
    canvas = Canvas(strips)
    light = canvas.light

    hat = Polygon(HAT)
    hat_tip = Polygon(HAT, sides=3)
    ears = [Polygon(SKIN, soft=CRISP * 1.5) for _ in EARS]
    inner_ears = [Polygon(INNER_EAR, soft=CRISP * 1.5) for _ in INNER_EARS]
    face = Ellipse(SKIN)
    cheeks = [Ellipse(CHEEKS) for _ in CHEEK_AT]
    eye_shapes = [Ellipse(EYE, soft=CRISP) for _ in EYES]
    glints = [Ellipse(GLINT, soft=CRISP) for _ in EYES]
    nose = Ellipse(NOSE, soft=CRISP)
    mouth = Ellipse(MOUTH, soft=CRISP)
    corners = [Ellipse(MOUTH, soft=CRISP) for _ in range(2)]
    tongue = Ellipse(TONGUE, soft=CRISP)
    brim = Ellipse(BRIM)
    pom = Ellipse(POM_POM)

    scene_start = utime.ticks_ms()
    eyes = Eyes(0.0)
    mood = Mood(0.0)
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
        talk, giggle, dy = mood.update(t)
        # Squinting with laughter.
        opened = min(opened, 1.0 - 0.55 * giggle)

        # The pom-pom lags behind the head's bounce.
        pom_v += (stiffness * (dy - pom_y) - damping * pom_v) * dt
        pom_y += pom_v * dt

        x, y, rx, ry = FACE
        flick = EAR_WIGGLE * giggle * math.sin(2 * math.pi * 6.0 * t)
        for ear, (a, b, c, tip) in zip(ears + inner_ears, EARS + INNER_EARS):
            ear.set([(a[0], a[1] + dy), (b[0], b[1] + dy), (c[0], c[1] + dy),
                     (tip[0], tip[1] + dy + flick)])
        hat.set([(px, py + dy) for px, py in HAT_BODY])
        hat_tip.set([(px, py + dy + (pom_y - dy) * (px - 14.6) / 6.4) for px, py in HAT_TIP])
        face.set(x, y + dy, rx, ry)
        for cheek, (cx, cy) in zip(cheeks, CHEEK_AT):
            cheek.set(cx, cy + dy, CHEEK_R, CHEEK_R * 0.8, CHEEK_ALPHA * (1 + 0.6 * giggle))
        for i, (ex, ey) in enumerate(EYES):
            # Closed, an eye is a dark line.
            ex += LOOK_REACH[0] * look_x
            ey += dy + LOOK_REACH[1] * look_y
            eye_shapes[i].set(ex, ey, EYE_SIZE[0], EYE_SIZE[1] * max(0.2, opened))
            gx, gy, gr, ga = GLINT_AT
            glints[i].set(ex + gx, ey + gy * opened, gr, gr, ga * max(0.0, opened * 2 - 1))
        nose.set(NOSE_AT[0], NOSE_AT[1] + dy, NOSE_AT[2], NOSE_AT[2])
        # The mouth: a dark line with its corners turned up; open, it
        # grows down into an oval with a tongue at the bottom.
        mx, my, mw = SMILE_AT
        mouth.set(mx, my + dy - 0.35 * talk, mw - 0.6 * talk, 0.5 + 0.6 * talk)
        for side, corner in zip((-1, 1), corners):
            corner.set(mx + side * (CORNERS_DX - 0.8 * talk), my + dy + 1.0 - 0.4 * talk,
                       CORNER_R, CORNER_R)
        tongue.set(mx, my + dy - 0.7, 0.8, 0.4, ease((talk - 0.3) / 0.5))
        brim.set(BRIM_AT[0], BRIM_AT[1] + dy, BRIM_AT[2], BRIM_AT[3])
        pom.set(POM_AT[0], POM_AT[1] + pom_y, POM_AT[2], POM_AT[2])

        canvas.clear()
        # Ears last of the head, over the edges of the face and brim.
        for shape in (hat, hat_tip, face, brim, ears[0], ears[1], inner_ears[0], inner_ears[1],
                      cheeks[0], cheeks[1],
                      eye_shapes[0], eye_shapes[1], glints[0], glints[1],
                      nose, mouth, corners[0], corners[1], tongue, pom):
            shape.draw(light)
        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
