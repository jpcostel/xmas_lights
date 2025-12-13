import time
import urandom

ROWS = 25
COLS = 8
NUM_FLAKES = 30     # how many snowflakes to animate
FALL_SPEED = 0.1    # delay between frames


# ------------------------
# Mapping function
# ------------------------
 
def grid_to_index(row, col):
    if row < 13:
        strand = 0
        base = 0
    else:
        strand = 1
        base = 100
        row -= 13

    if row % 2 == 0:
        idx_within_row = (COLS - 1) - col
    else:
        idx_within_row = col

    index = row * COLS + idx_within_row
    return strand, index


# ------------------------
# Snowflake simulation
# ------------------------

def make_flake():
    """Create a new snowflake near the top with random column."""
    return {
        "row": urandom.getrandbits(5) % 3 + (ROWS - 3),   # top 3 rows only
        "col": urandom.getrandbits(3) % COLS
    }


def snowfall_effect(strips):
    # Initialize flakes
    flakes = [make_flake() for _ in range(NUM_FLAKES)]

    while True:
        # Clear
        for strip in strips:
            strip.fill((0,0,0))

        # Draw flakes
        for f in flakes:
            strand, idx = grid_to_index(f["row"], f["col"])
            strips[strand][idx] = (120, 120, 255)  # icy white/blue

        # Write out
        for strip in strips:
            strip.write()

        # Move flakes
        for f in flakes:
            if urandom.getrandbits(2) == 0:
                f["col"] = max(0, min(COLS-1, f["col"] + (urandom.getrandbits(1)*2 - 1)))  # optional side>

            f["row"] -= 1

            if f["row"] < 0:
                f.update(make_flake())

        time.sleep(FALL_SPEED)