import math
import random
import utime
from wiring import show_all
from grid import grid_to_pixel, ROWS, COLS

# ============================================================
# CONFIGURATION
# ============================================================

SKIN_COLOR = (255, 70, 0)      # pumpkin orange

PUPIL_COLOR = (255, 200, 60)   # glowing pupils inside the dark eye sockets
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
#   E  eye socket (void the pupils move around in; animated faces only)

FACES = [
    # 0: classic - triangle eyes and nose
    [
        ".........................",
        "......#...........#......",
        ".....###.........###.....",
        "....#####.......#####....",
        "...#######.....#######...",
        "............#............",
        "...........###...........",
        ".........................",
    ],
    # 1: scary - angry slanted eyes, downward nose
    [
        ".........................",
        "..##.................##..",
        "..#####...........#####..",
        "...#######.....#######...",
        "....######.....######....",
        "...........###...........",
        "............#............",
        ".........................",
    ],
    # 2: happy - round eyes, triangle nose
    [
        ".........................",
        ".....###.........###.....",
        "....#####.......#####....",
        "....#####.......#####....",
        ".....###.........###.....",
        "............#............",
        "...........###...........",
        ".........................",
    ],
]

WATCHING_FACES = [
    # 0: round eyes
    [
        ".........................",
        "....EEEE.........EEEE....",
        "...EEEEEE.......EEEEEE...",
        "...EEEEEE.......EEEEEE...",
        "....EEEE.........EEEE....",
        "............#............",
        "...........###...........",
        ".........................",
    ],
    # 1: scary - same eyes and nose as FACES[1]
    [
        ".........................",
        "..EE.................EE..",
        "..EEEEE...........EEEEE..",
        "...EEEEEEE.....EEEEEEE...",
        "....EEEEEE.....EEEEEE....",
        "...........###...........",
        "............#............",
        ".........................",
    ],
]


def _draw_face(strips, face):
    for r, line in enumerate(face):
        row = ROWS - 1 - r
        for col, ch in enumerate(line):
            strand, index = grid_to_pixel(row, col)
            strips[strand][index] = SKIN_COLOR if ch == "." else (0, 0, 0)


# ============================================================
# STATIC JACK-O'-LANTERN
# ============================================================

def jack_o_lantern(strips, face=0):
    """Draw one of FACES and return; the strips hold the image."""
    _draw_face(strips, FACES[face])
    show_all(strips)


# ============================================================
# WATCHING JACK-O'-LANTERN (pupils look around the room)
# ============================================================

def _eye_sockets(face):
    """Group the 'E' cells into left/right eyes.

    Returns [(center_x, center_y, top_row, height, cells, cell_set)], where
    cells is a list of (col, row, strand, index) and cell_set holds the
    (col, row) pairs for quick "is this inside the socket" checks.
    """
    eyes = {}
    for r, line in enumerate(face):
        row = ROWS - 1 - r
        for col, ch in enumerate(line):
            if ch == "E":
                strand, index = grid_to_pixel(row, col)
                eyes.setdefault(col >= COLS // 2, []).append((col, row, strand, index))

    # Centers are snapped to the nearest half pixel: mirrored, lopsided
    # sockets (the scary eyes) have centroids like 5.3 and 18.7, and the
    # same gaze offset would then put one pupil on an LED and the other
    # split between two, so they'd look out of sync.
    sockets = []
    for side in sorted(eyes):
        cells = eyes[side]
        rows = [c[1] for c in cells]
        sockets.append((
            round(2 * sum(c[0] for c in cells) / len(cells)) / 2,
            round(2 * sum(rows) / len(rows)) / 2,
            max(rows),
            max(rows) - min(rows) + 1,
            cells,
            set((c[0], c[1]) for c in cells),
        ))
    return sockets


def _pick_gaze(sockets):
    """Random pupil offset that keeps both pupils inside their sockets.

    Sockets can be any shape (the scary eyes are slanted), so candidates
    are drawn from the socket's bounding box and kept only if the nearest
    cell to each pupil is part of that socket.
    """
    if random.random() < CENTER_GAZE_PROB:
        return 0.0, 0.0
    cells = sockets[0][4]
    reach_x = (max(c[0] for c in cells) - min(c[0] for c in cells)) / 2
    reach_y = (max(c[1] for c in cells) - min(c[1] for c in cells)) / 2
    for _ in range(20):
        x = random.uniform(-reach_x, reach_x)
        y = random.uniform(-reach_y, reach_y)
        if all((round(cx + x), round(cy + y)) in cell_set
               for cx, cy, _, _, _, cell_set in sockets):
            return x, y
    return 0.0, 0.0


def watching_jack(strips, face=0):
    _draw_face(strips, WATCHING_FACES[face])
    sockets = _eye_sockets(WATCHING_FACES[face])

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
            to_x, to_y = _pick_gaze(sockets)
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
        for cx, cy, top, height, cells, _ in sockets:
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
                strips[strand][index] = (
                    int(PUPIL_COLOR[0] * b * (1 - covered) + SKIN_COLOR[0] * covered),
                    int(PUPIL_COLOR[1] * b * (1 - covered) + SKIN_COLOR[1] * covered),
                    int(PUPIL_COLOR[2] * b * (1 - covered) + SKIN_COLOR[2] * covered),
                )

        show_all(strips)

        elapsed = utime.ticks_diff(utime.ticks_ms(), frame_start)
        sleep_ms = FRAME_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)
