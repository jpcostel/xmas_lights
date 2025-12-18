import time, random, math

ROWS = 8
COLS = 25

CUTOFF = 0.5        # interpolation cutoff

SNOW_COLOR = (255, 200, 16)
MAX_FLAKES = 150
SPAWN_INTERVAL = 0.016   # seconds
DT = 0.016             # frame time
INTENSITY = 25      # max percentage of total columns

def grid_to_pixel(row, col):
    """
    row: 0 = bottom, 7 = top
    col: 0 = left, 24 = right
    returns: (strand, index)
    """

    if row < 4:
        strand = 0
        local_row = row
    else:
        strand = 1
        local_row = row - 4

    if local_row % 2 == 0:
        # right → left
        index = local_row * COLS + (COLS - 1 - col)
    else:
        # left → right
        index = local_row * COLS + col

    return strand, index

class Snowflake:
    def __init__(self, col):
        self.col = col
        self.y = ROWS + random.uniform(0.0, 4.0)
        self.speed = random.uniform(2.5, 10.0)
        self.base = random.uniform(0.3, 1.0)
        self.phase = random.uniform(0, 2*math.pi)
        self.rate = random.uniform(1.0, 3.0)

    def update(self, dt):
        self.y -= self.speed * dt
        self.phase += self.rate * dt

    def brightness(self):
        return self.base * (0.6 + 0.4 * math.sin(self.phase))


def snowfall_effect(strips):
    flakes = []
    last_spawn = time.time()
    last_col = 0
    while True:
        now = time.time()
        dt = DT

        # ---- Spawn new flakes ----
        if now - last_spawn > SPAWN_INTERVAL:
            for _ in range(random.randint(1, 5)):
                if len(flakes) < MAX_FLAKES:
                    for b in range(random.randrange(int((INTENSITY/100)*25))):
                        col = random.randrange(COLS)
                        flakes.append(Snowflake(random.randrange(COLS)))
            last_spawn = now

        # ---- Clear LED grid ----
        accum = [[0.0 for _ in range(COLS)] for _ in range(ROWS)]

        # ---- Update flakes ----
        alive = []
        for f in flakes:
            f.update(dt)
            if f.y < -1.0:
                continue

            b = f.brightness()
            row = int(f.y)

            # vertical interpolation
            frac = f.y - row
            if 0 <= row < ROWS:
                if frac > CUTOFF:
                    accum[row][f.col] += b * frac
            if 0 <= row - 1 < ROWS:
                if (1.0 - frac) > CUTOFF:
                    accum[row - 1][f.col] += b * (1.0 - frac)

            alive.append(f)

        flakes = alive

        # ---- Render to LEDs ----
        for r in range(ROWS):
            for c in range(COLS):
                v = min(1.0, accum[r][c])
                color = (
                    int(SNOW_COLOR[0] * v),
                    int(SNOW_COLOR[1] * v),
                    int(SNOW_COLOR[2] * v),
                )
                strand, idx = grid_to_pixel(r, c)
                strips[strand][idx] = color

        for s in strips:
            s.write()
        end = time.time()
        loop_time = end - now
        time.sleep(DT - loop_time)
