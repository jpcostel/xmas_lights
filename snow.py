import time
import urandom
from wiring import *
from grid import *

NUM_FLAKES = 28
FALL_DELAY = 0.08

def new_flake():
    return {
        "row": 7,
        "col": urandom.getrandbits(5) % COLS
    }

def snowfall_effect(strips):
    flakes = [new_flake() for _ in range(NUM_FLAKES)]

    while True:
        # Clear background
        for s in strips:
            s.fill((0, 0, 0))

        # Draw flakes
        for f in flakes:
            strand, idx = grid_to_pixel(f["row"], f["col"])
            strips[strand][idx] = (180, 180, 255)

        for s in strips:
            s.write()

        # Move flakes
        for f in flakes:
            # gentle wind
            if urandom.getrandbits(3) == 0:
                f["col"] += -1 if urandom.getrandbits(1) == 0 else 1
                f["col"] = max(0, min(COLS - 1, f["col"]))

            f["row"] -= 1

            if f["row"] < 0:
                f.update(new_flake())

        time.sleep(FALL_DELAY)
