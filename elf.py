import array
import utime
from canvas import Canvas
from faces import Eyes
from shapes import Ellipse, Polygon

# ============================================================
# CONFIGURATION
# ============================================================
# One of Santa's elves, face on: pointy ears, a floppy hat with a
# pom-pom, rosy cheeks and a smile. The eyes blink and look around.
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
LOOK_REACH = (0.5, 0.25)                   # how far the eyes move
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

FRAME_MS = 16                  # ~60 FPS


# ============================================================
# MAIN EFFECT LOOP
# ============================================================

def santas_elf(strips):
    canvas = Canvas(strips)
    light = canvas.light

    # Everything but the eyes stays still: paint it once and copy it in
    # each frame. Ears go over the edges of the face and brim.
    still = [Polygon(HAT, HAT_BODY), Polygon(HAT, HAT_TIP, sides=3),
             Ellipse(SKIN, *FACE), Ellipse(BRIM, *BRIM_AT)]
    still += [Polygon(SKIN, list(ear), soft=CRISP * 1.5) for ear in EARS]
    still += [Polygon(INNER_EAR, list(ear), soft=CRISP * 1.5) for ear in INNER_EARS]
    still += [Ellipse(CHEEKS, x, y, CHEEK_R, CHEEK_R * 0.8, CHEEK_ALPHA) for x, y in CHEEK_AT]
    still.append(Ellipse(NOSE, NOSE_AT[0], NOSE_AT[1], NOSE_AT[2], NOSE_AT[2], soft=CRISP))
    # The smile: a dark line with its corners turned up a row.
    mx, my, mw = SMILE_AT
    still.append(Ellipse(MOUTH, mx, my, mw, 0.5, soft=CRISP))
    still += [Ellipse(MOUTH, mx + side * CORNERS_DX, my + 1.0, CORNER_R, CORNER_R, soft=CRISP)
              for side in (-1, 1)]
    still.append(Ellipse(POM_POM, POM_AT[0], POM_AT[1], POM_AT[2], POM_AT[2]))
    for shape in still:
        shape.draw(light)
    face = array.array("H", light)

    eye_shapes = [Ellipse(EYE, soft=CRISP) for _ in EYES]
    glints = [Ellipse(GLINT, soft=CRISP) for _ in EYES]
    scene_start = utime.ticks_ms()
    eyes = Eyes(0.0)

    while True:
        frame_start = utime.ticks_ms()
        t = utime.ticks_diff(frame_start, scene_start) / 1000

        opened, look_x, look_y = eyes.update(t)
        light[:] = face
        for i, (ex, ey) in enumerate(EYES):
            # Closed, an eye is a dark line.
            ex += LOOK_REACH[0] * look_x
            ey += LOOK_REACH[1] * look_y
            eye_shapes[i].set(ex, ey, EYE_SIZE[0], EYE_SIZE[1] * max(0.2, opened))
            gx, gy, gr, ga = GLINT_AT
            glints[i].set(ex + gx, ey + gy * opened, gr, gr, ga * max(0.0, opened * 2 - 1))
            eye_shapes[i].draw(light)
            glints[i].draw(light)
        canvas.show()

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
