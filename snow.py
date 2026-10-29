import time, random, math
from wiring import show_all, pixel_map, restore

ROWS = 8
COLS = 25

CUTOFF = 0.5        # interpolation cutoff

SNOW_COLOR = (255,225,255)
SNOW_COLORS = ((255,255,0), (0,0,255), (255,0,0), (0,255,0), (0,255,255), (255,0,255))
MAX_FLAKES = 150
SPAWN_INTERVAL = 0.016   # seconds
DT = 0.016             # frame time
INTENSITY = 50      # max percentage of total columns

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
    pixels = pixel_map(strips)
    blank = [bytes(len(s.buf)) for s in strips]
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
        restore(strips, blank)

        # ---- Update flakes, drawing each straight into the strip bytes ----
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
                    buf, ro, go, bo = pixels[row][f.col]
                    buf[ro] = int(f.color[0] * frac * b)
                    buf[go] = int(f.color[1] * frac * b)
                    buf[bo] = int(f.color[2] * frac * b)
            if 0 <= row - 1 < ROWS:
                if (1.0 - frac) > CUTOFF:
                    buf, ro, go, bo = pixels[row - 1][f.col]
                    buf[ro] = int(f.color[0] * (1.0 - frac) * b)
                    buf[go] = int(f.color[1] * (1.0 - frac) * b)
                    buf[bo] = int(f.color[2] * (1.0 - frac) * b)
            alive.append(f)

        flakes = alive

        show_all(strips)
        end = time.time()
        loop_time = end - now
        time.sleep(DT - loop_time)
