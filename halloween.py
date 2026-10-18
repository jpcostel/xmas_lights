import math
import random
import utime
from wiring import show_all
from grid import grid_to_pixel, ROWS, COLS

# ============================================================
# CONFIGURATION
# ============================================================

SKIN_COLOR = (255, 70, 0)      # base pumpkin orange
SKIN_HUE_JITTER = 30           # +/- green spread: redder <-> yellower pixels
SKIN_SPECKLE = 0.10            # random per-pixel brightness dip
RIB_SPACING = 6                # columns between vertical pumpkin ribs
RIB_DEPTH = 0.15               # how much darker the rib grooves are
EDGE_SHADE = 0.35              # darkening toward the sides (round pumpkin)

PUPIL_COLOR = (255, 200, 60)   # glowing pupils inside the dark eye sockets
GAZE_X = 2.0                   # max pupil travel from socket center (pixels)
GAZE_Y = 1.0
CENTER_GAZE_PROB = 0.3         # chance the next glance is straight ahead
HOLD_MS = (400, 2500)          # how long the eyes rest on each spot
SACCADE_MS = 90                # base duration of a glance...
SACCADE_MS_PER_PX = 50         # ...plus this much per pixel travelled
BLINK_EVERY_MS = (2500, 7000)
BLINK_MS = 220

FRAME_MS = 33                  # ~30 FPS

# ============================================================
# FACE DESIGNS
# ============================================================
# Drawn top row first, so they read the way they look on the wall.
#   .  pumpkin skin
#   #  void (LED off)
#   E  eye socket (void the pupils move around in; animated face only)

FACES = [
    # 0: classic - triangle eyes and nose, toothy grin
    [
        ".........................",
        "......#...........#......",
        ".....###.........###.....",
        "....#####...#...#####....",
        "...........###...........",
        "...##...............##...",
        "....###.#########.###....",
        ".....######...######.....",
    ],
    # 1: scary - angry slanted eyes, nostrils, jagged teeth
    [
        ".........................",
        "...##...............##...",
        "...#####.........#####...",
        "....######.....######....",
        "...........#.#...........",
        "..#####################..",
        "...#.#.#.#.#.#.#.#.#.#...",
        ".........................",
    ],
    # 2: happy - round eyes, button nose, wide smile
    [
        ".........................",
        ".....###.........###.....",
        "....#####.......#####....",
        ".....###.........###.....",
        "............#............",
        "..##.................##..",
        "...####...........####...",
        ".......###########.......",
    ],
]

WATCHING_FACE = [
    ".........................",
    "....EEEE.........EEEE....",
    "...EEEEEE.......EEEEEE...",
    "....EEEE.........EEEE....",
    "...........###...........",
    "...##...............##...",
    "....###.#########.###....",
    ".....######...######.....",
]


# ============================================================
# PUMPKIN SKIN
# ============================================================

def _pumpkin_skin():
    """Orange per grid cell with ribs, rounded shading, and speckle.

    Uses its own LCG rather than random.seed() so the texture is the same
    every time without making the other effects' randomness repeatable.
    """
    seed = 0x5EED
    mid = (COLS - 1) / 2
    skin = []
    for row in range(ROWS):
        line = []
        for col in range(COLS):
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            speckle = (seed & 0xFFFF) / 0xFFFF
            hue = ((seed >> 16) & 0x7FFF) / 0x7FFF

            rib = 1.0 - RIB_DEPTH * 0.5 * (1 - math.cos(2 * math.pi * (col - mid) / RIB_SPACING))
            edge = 1.0 - EDGE_SHADE * ((col - mid) / mid) ** 2
            shade = rib * edge * (1.0 - SKIN_SPECKLE * speckle)

            g = max(0, SKIN_COLOR[1] + int((hue - 0.5) * 2 * SKIN_HUE_JITTER))
            line.append((
                int(SKIN_COLOR[0] * shade),
                int(g * shade),
                int(SKIN_COLOR[2] * shade),
            ))
        skin.append(line)
    return skin


def _draw_face(strips, face, skin):
    for r, line in enumerate(face):
        row = ROWS - 1 - r
        for col, ch in enumerate(line):
            strand, index = grid_to_pixel(row, col)
            strips[strand][index] = skin[row][col] if ch == "." else (0, 0, 0)


# ============================================================
# STATIC JACK-O'-LANTERN
# ============================================================

def jack_o_lantern(strips, face=0):
    """Draw one of FACES and return; the strips hold the image."""
    _draw_face(strips, FACES[face], _pumpkin_skin())
    show_all(strips)


# ============================================================
# WATCHING JACK-O'-LANTERN (pupils look around the room)
# ============================================================

def _eye_sockets(face):
    """Group the 'E' cells into left/right eyes.

    Returns [(center_x, center_y, top_row, height, cells)], where cells is
    a list of (col, row, strand, index).
    """
    eyes = {}
    for r, line in enumerate(face):
        row = ROWS - 1 - r
        for col, ch in enumerate(line):
            if ch == "E":
                strand, index = grid_to_pixel(row, col)
                eyes.setdefault(col >= COLS // 2, []).append((col, row, strand, index))

    sockets = []
    for side in sorted(eyes):
        cells = eyes[side]
        rows = [c[1] for c in cells]
        sockets.append((
            sum(c[0] for c in cells) / len(cells),
            sum(rows) / len(rows),
            max(rows),
            max(rows) - min(rows) + 1,
            cells,
        ))
    return sockets


def _pick_gaze():
    if random.random() < CENTER_GAZE_PROB:
        return 0.0, 0.0
    while True:
        x = random.uniform(-1.0, 1.0)
        y = random.uniform(-1.0, 1.0)
        if x * x + y * y <= 1.0:
            return x * GAZE_X, y * GAZE_Y


def watching_jack(strips):
    skin = _pumpkin_skin()
    _draw_face(strips, WATCHING_FACE, skin)
    sockets = _eye_sockets(WATCHING_FACE)

    now = utime.ticks_ms()
    gx, gy = 0.0, 0.0
    from_x, from_y = gx, gy
    to_x, to_y = gx, gy
    move_start = now
    move_ms = 1
    next_move = utime.ticks_add(now, random.randint(*HOLD_MS))
    next_blink = utime.ticks_add(now, random.randint(*BLINK_EVERY_MS))

    while True:
        frame_start = utime.ticks_ms()

        # ----------------------------------------------------
        # GAZE: hold, then glance (eased) to a new spot
        # ----------------------------------------------------
        if utime.ticks_diff(frame_start, next_move) >= 0:
            from_x, from_y = gx, gy
            to_x, to_y = _pick_gaze()
            dist = math.sqrt((to_x - from_x) ** 2 + (to_y - from_y) ** 2)
            move_start = frame_start
            move_ms = int(SACCADE_MS + SACCADE_MS_PER_PX * dist)
            next_move = utime.ticks_add(frame_start, move_ms + random.randint(*HOLD_MS))

        t = min(1.0, utime.ticks_diff(frame_start, move_start) / move_ms)
        ease = t * t * (3 - 2 * t)
        gx = from_x + (to_x - from_x) * ease
        gy = from_y + (to_y - from_y) * ease

        # ----------------------------------------------------
        # BLINK: lid sweeps down over the socket and back up
        # ----------------------------------------------------
        lid = 0.0
        since_blink = utime.ticks_diff(frame_start, next_blink)
        if since_blink >= 0:
            if since_blink < BLINK_MS:
                lid = math.sin(math.pi * since_blink / BLINK_MS)
            else:
                next_blink = utime.ticks_add(frame_start, random.randint(*BLINK_EVERY_MS))

        # ----------------------------------------------------
        # DRAW EYES (the rest of the face never changes)
        # ----------------------------------------------------
        for cx, cy, top, height, cells in sockets:
            px = cx + gx
            py = cy + gy
            # Bilinear spread so the pupil glides between pixels, scaled so
            # the nearest cells are always full brightness (a pupil between
            # two LEDs lights both rather than two half-bright ones). The
            # peak is computed unclipped, so a pupil sliding behind the
            # socket edge still fades out.
            peak = (1 - abs(px - round(px))) * (1 - abs(py - round(py)))
            for col, row, strand, index in cells:
                w = max(0.0, 1 - abs(col - px)) * max(0.0, 1 - abs(row - py))
                b = min(1.0, w / peak)
                covered = min(1.0, max(0.0, lid * height - (top - row)))
                s = skin[row][col]
                strips[strand][index] = (
                    int(PUPIL_COLOR[0] * b * (1 - covered) + s[0] * covered),
                    int(PUPIL_COLOR[1] * b * (1 - covered) + s[1] * covered),
                    int(PUPIL_COLOR[2] * b * (1 - covered) + s[2] * covered),
                )

        show_all(strips)

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
