import time, random, math

ROWS = 10
COLS = 25

CUTOFF = 0.5        # interpolation cutoff

SNOW_COLOR = (255,225,255)
SNOW_COLORS = ((255,255,0), (0,0,255), (255,0,0), (0,255,0), (0,255,255), (255,0,255))
MAX_FLAKES = 150
SPAWN_INTERVAL = 0.016   # seconds
DT = 0.016             # frame time
INTENSITY = 50      # max percentage of total columns

def grid_to_pixel(row, col):
    """
    row: 0 = bottom, 7 = top
    col: 0 = left, 24 = right
    returns: (strand, index)
    """

    strand = 0
    local_row = row

    if local_row % 2 == 0:
        # right → left
        index = local_row * COLS + (COLS - 1 - col)
    else:
        # left → right
        index = local_row * COLS + col

    return strand, index

class Snowflake:
    def __init__(self, col, colorful):
        self.col = col
        self.y = ROWS + random.uniform(0.0, 4.0)
        self.speed = random.uniform(4.0, 16.0)
        self.base = random.uniform(0.3, 1.0)
        self.phase = random.uniform(0, 2*math.pi)
        self.rate = random.uniform(1.0, 3.0)
        if colorful:
            self.color = SNOW_COLORS[random.randint(0,(len(SNOW_COLORS) - 1))]
        else:
            self.color = SNOW_COLOR

    def update(self, dt):
        self.y -= self.speed * dt
        self.phase += self.rate * dt

    def brightness(self):
        return self.base * (0.6 + 0.4 * math.sin(self.phase))


def snowfall_effect(strips, colorful=False):
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
                        flakes.append(Snowflake(random.randrange(COLS), colorful))
            last_spawn = now

        # ---- Clear LED grid ----
        accum = [[[0.0, 0.0, 0.0] for _ in range(COLS)] for _ in range(ROWS)]

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
                    accum[row][f.col][0] = f.color[0] * frac * b
                    accum[row][f.col][1] = f.color[1] * frac * b
                    accum[row][f.col][2] = f.color[2] * frac * b
            if 0 <= row - 1 < ROWS:
                if (1.0 - frac) > CUTOFF:
                    accum[row - 1][f.col][0] = f.color[0] * (1.0 - frac) * b
                    accum[row - 1][f.col][1] = f.color[1] * (1.0 - frac) * b
                    accum[row - 1][f.col][2] = f.color[2] * (1.0 - frac) * b
            alive.append(f)

        flakes = alive

        # ---- Render to LEDs ----
        for r in range(ROWS):
            for c in range(COLS):
                strand, idx = grid_to_pixel(r, c)
                strips[strand][idx] = (int(accum[r][c][0]), int(accum[r][c][1]), int(accum[r][c][2]))

        for s in strips:
            s.write()
        end = time.time()
        loop_time = end - now
        time.sleep(DT - loop_time)
