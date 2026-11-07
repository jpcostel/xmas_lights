#!/usr/bin/env python3
"""Live weather for the mantle's Live Weather scene.

Runs as its own long-lived process on the Pi (weather_service.service).
Every few minutes it fetches the local weather from Open-Meteo (free, no
key), works out how the scene should look -- sky colors for the sun's
real height, cloud cover, rain, snow, the wind as it crosses the mantle,
where the sun and moon are -- and, while the Live Weather scene is
running, sends that to the Pico as a line like

    #WX top=1,2,12 cloud=0.42 rain=2.5 wind=3.1,-0.4 ...

The scene reads these lines from its serial input and eases toward them.
They start with # so they're harmless comments if the REPL reads one.

The web page (/weather) shows the latest state and can override any
input -- rain, snow, wind, clouds, time of day -- to preview the scene.
"""
import json
import logging
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pico_ctrl
from scenes import SCENES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("weather")

# ============================================================
# CONFIGURATION
# ============================================================

LATITUDE = 42.19234
LONGITUDE = -83.80752
FACING = 90                    # compass bearing you face looking at the mantle (east)

FETCH_EVERY_S = 600
SEND_EVERY_S = 30              # the sun moves; resend this often while the scene runs
# After a scene command, ask whether Live Weather is listening at these
# times (seconds): it takes a moment to start.
ASK_AFTER_S = (1, 3, 6, 12)
QUESTION, ANSWER = "#?", "#WX!"
STALE_S = 3 * 3600             # after this long without a fetch, ease toward calm

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "weather_state.json")
OVERRIDE_FILE = os.path.join(HERE, "weather_override.json")
SCENE_CMD = SCENES["live_weather"]["cmd"]

# Inputs the web page can override, with their units.
INPUTS = {
    "rain": "mm/h",
    "snow": "cm/h",
    "cloud": "%",
    "cloud_low": "%",
    "cloud_high": "% (mid or high)",
    "wind_speed": "m/s",
    "wind_dir": "° from",
    "gust": "m/s",
    "visibility": "m",
    "code": "WMO",
    "temperature": "°C",
    "hour": "local time",
}

CALM = {"rain": 0.0, "snow": 0.0, "cloud": 20.0, "cloud_low": 20.0, "cloud_high": 10.0, "wind_speed": 1.0, "wind_dir": 270.0,
        "gust": 2.0, "visibility": 20000.0, "code": 1, "temperature": 10.0}

API = "https://api.open-meteo.com/v1/forecast"
NOW_VARS = ("temperature_2m,precipitation,rain,showers,snowfall,weather_code,cloud_cover,"
            "cloud_cover_low,cloud_cover_mid,cloud_cover_high,"
            "wind_speed_10m,wind_direction_10m,wind_gusts_10m,visibility")
STEP_VARS = "precipitation,snowfall,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,visibility"


# ============================================================
# FETCHING
# ============================================================

def fetch():
    query = urllib.parse.urlencode({
        "latitude": LATITUDE, "longitude": LONGITUDE, "current": NOW_VARS,
        "minutely_15": STEP_VARS, "past_minutely_15": 2, "forecast_minutely_15": 4,
        "timezone": "UTC", "wind_speed_unit": "ms",
    })
    with urllib.request.urlopen(f"{API}?{query}", timeout=20) as reply:
        return json.load(reply)


def _blend_angle(a, b, f):
    d = (b - a + 180) % 360 - 180
    return (a + d * f) % 360


def observe(data, now):
    """The weather now, from a fetch: the 15-minute steps either side of
    now blended together, and cloud cover from the latest reading."""
    cur = data["current"]
    obs = {
        "rain": 4 * (cur["rain"] + cur["showers"]),     # per 15 min -> per hour
        "snow": 4 * cur["snowfall"],
        "cloud": cur["cloud_cover"],
        "cloud_low": cur["cloud_cover_low"],
        "cloud_high": max(cur["cloud_cover_mid"], cur["cloud_cover_high"]),
        "wind_speed": cur["wind_speed_10m"],
        "wind_dir": cur["wind_direction_10m"],
        "gust": cur["wind_gusts_10m"],
        "visibility": cur["visibility"],
        "code": cur["weather_code"],
        "temperature": cur["temperature_2m"],
    }
    steps = data.get("minutely_15") or {}
    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in steps.get("time", [])]
    for i in range(len(times) - 1):
        if times[i] <= now < times[i + 1]:
            f = (now - times[i]) / (times[i + 1] - times[i])

            def at(key):
                a, b = steps[key][i], steps[key][i + 1]
                if a is None or b is None:
                    return a if b is None else b
                return a + (b - a) * f

            precip = at("precipitation")
            snow = at("snowfall")
            if precip is not None and snow is not None:
                obs["snow"] = 4 * snow
                # Snowfall is in cm of snow, about 7x its melted mm.
                obs["rain"] = max(0.0, 4 * precip - 4 * snow / 7)
            for key, name in (("wind_speed", "wind_speed_10m"), ("gust", "wind_gusts_10m"),
                              ("visibility", "visibility")):
                v = at(name)
                if v is not None:
                    obs[key] = v
            a, b = steps["wind_direction_10m"][i], steps["wind_direction_10m"][i + 1]
            if a is not None and b is not None:
                obs["wind_dir"] = _blend_angle(a, b, f)
            code = steps["weather_code"][i if f < 0.5 else i + 1]
            if code is not None:
                obs["code"] = code
            break
    return obs


# ============================================================
# SUN AND MOON
# ============================================================
# Low-precision formulas (good to about a degree), from the Astronomical
# Almanac's approximations.

def _days(when):
    return (when - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400


def _alt_az(ra, dec, d, lat, lon):
    """Height and compass bearing (degrees) of a sky position."""
    lst = math.radians((280.46061837 + 360.98564736629 * d + lon) % 360)
    ha = lst - ra
    lat = math.radians(lat)
    alt = math.asin(math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.sin(ha) * math.cos(dec),
                    math.cos(lat) * math.sin(dec) - math.sin(lat) * math.cos(dec) * math.cos(ha))
    return math.degrees(alt), math.degrees(az) % 360


def _sun_longitude(d):
    g = math.radians((357.529 + 0.98560028 * d) % 360)
    return math.radians((280.459 + 0.98564736 * d + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360)


def sun_position(when, lat=LATITUDE, lon=LONGITUDE):
    d = _days(when)
    sl = _sun_longitude(d)
    e = math.radians(23.439 - 0.00000036 * d)
    ra = math.atan2(math.cos(e) * math.sin(sl), math.cos(sl))
    dec = math.asin(math.sin(e) * math.sin(sl))
    return _alt_az(ra, dec, d, lat, lon)


def moon_position(when, lat=LATITUDE, lon=LONGITUDE):
    """Height, bearing, the fraction of it lit, and whether it's waxing."""
    d = _days(when)
    m = math.radians((134.963 + 13.064993 * d) % 360)
    f = math.radians((93.272 + 13.229350 * d) % 360)
    ml = math.radians((218.316 + 13.176396 * d + 6.289 * math.sin(m)) % 360)
    mb = math.radians(5.128 * math.sin(f))
    e = math.radians(23.439 - 0.00000036 * d)
    ra = math.atan2(math.sin(ml) * math.cos(e) - math.tan(mb) * math.sin(e), math.cos(ml))
    dec = math.asin(math.sin(mb) * math.cos(e) + math.cos(mb) * math.sin(e) * math.sin(ml))
    alt, az = _alt_az(ra, dec, d, lat, lon)
    # Parallax: the moon is close enough to sit about a degree lower.
    alt -= 0.95 * math.cos(math.radians(alt))
    elong = (ml - _sun_longitude(d)) % (2 * math.pi)
    return alt, az, (1 - math.cos(elong)) / 2, elong < math.pi


# ============================================================
# HOW IT LOOKS
# ============================================================
# Colors are 0-255 per channel as they'd look with gamma off.

# Sky by the sun's height (degrees): top of the mantle, then its bottom
# (the horizon), as if looking out the way it faces.
SKY = [
    (-18, (0, 0, 0), (0, 0, 0)),          # night: just stars
    (-12, (0, 0, 2), (1, 0, 4)),
    (-7, (1, 2, 10), (14, 4, 12)),        # deep blue over a rose glow
    (-3, (3, 7, 26), (70, 22, 10)),
    (0, (6, 14, 42), (120, 45, 10)),      # sunrise, sunset
    (4, (10, 26, 70), (110, 70, 25)),     # golden hour
    (12, (12, 36, 95), (50, 75, 95)),
    (35, (12, 40, 110), (40, 75, 110)),   # day
]
TWILIGHT_BEHIND = 0.35         # glow when the sun rises or sets behind you
OVERCAST = (30, 32, 37)        # a fully overcast daytime sky
CLOUD_DAY = (70, 70, 75)
CLOUD_GOLD = (150, 70, 45)     # lit from below near sunrise and sunset
CLOUD_NIGHT = (0, 0, 0)        # at night clouds just hide the stars
RAIN_DAY = (170, 195, 240)
RAIN_NIGHT = (70, 85, 120)     # still visible, just dimmer
SNOW_DAY = (230, 230, 245)
SNOW_NIGHT = (110, 110, 125)
STORM_DARK = 0.35              # cloud brightness in a thunderstorm
SUN_WHITE = (255, 205, 120)    # sunlight through a break in the clouds...
SUN_GOLD = (255, 140, 50)      # ...and with the sun low
BREAK_LIGHT = 0.6              # how bright it gets in a break
VIEW = 100                     # degrees either side of FACING that reach the grid's ends


def _mix(a, b, f):
    return tuple(x + (y - x) * f for x, y in zip(a, b))


def _smooth(lo, hi, v):
    f = min(1.0, max(0.0, (v - lo) / (hi - lo)))
    return f * f * (3 - 2 * f)


def _sky_at(alt):
    if alt <= SKY[0][0]:
        return SKY[0][1], SKY[0][2]
    for (a0, t0, b0), (a1, t1, b1) in zip(SKY, SKY[1:]):
        if alt <= a1:
            f = (alt - a0) / (a1 - a0)
            return _mix(t0, t1, f), _mix(b0, b1, f)
    return SKY[-1][1], SKY[-1][2]


def _ahead(az):
    """Degrees from straight ahead (-180..180, positive to the right)."""
    return (az - FACING + 180) % 360 - 180


def look(obs, when):
    """Everything the scene draws, from the weather and the time."""
    sun_alt, sun_az = sun_position(when)
    moon_alt, moon_az, moon_lit, waxing = moon_position(when)
    day = _smooth(-8, 8, sun_alt)
    cloud = min(1.0, max(0.0, obs["cloud"] / 100))
    code = int(obs["code"])
    storm = code >= 95
    rain, snow = obs["rain"], obs["snow"]
    # The report can name rain or snow but measure next to none.
    if rain < 0.1 and (51 <= code <= 67 or 80 <= code <= 82 or storm):
        rain = 0.2
    if snow < 0.05 and (71 <= code <= 77 or 85 <= code <= 86):
        snow = 0.1

    top, bottom = _sky_at(sun_alt)
    # The rose and gold glow is strongest when the sun's in front.
    glow = TWILIGHT_BEHIND + (1 - TWILIGHT_BEHIND) * (1 + math.cos(math.radians(_ahead(sun_az)))) / 2
    if sun_alt < 12:
        bottom = _mix(top, bottom, glow)
    grey = tuple(c * day for c in OVERCAST)
    top = _mix(top, grey, 0.6 * cloud)
    bottom = _mix(bottom, grey, 0.6 * cloud)

    golden = _smooth(-6, -1, sun_alt) * (1 - _smooth(4, 12, sun_alt))
    cloud_color = _mix(_mix(CLOUD_NIGHT, CLOUD_DAY, day), CLOUD_GOLD, golden * glow)
    dark = 1 - (1 - STORM_DARK) * (1 if storm else min(1.0, (rain + snow * 2) / 10))
    cloud_color = tuple(c * dark for c in cloud_color)

    # Breaks where the sun nearly shows through: most often in a mostly
    # cloudy sky, now and then under full overcast, never in rain.
    breaks = _smooth(-2, 6, sun_alt) * _smooth(0.4, 0.7, cloud) * (1 - 0.65 * _smooth(0.9, 1.0, cloud))
    breaks *= 0 if storm else 1 - min(1.0, (rain + snow * 3) / 1.5)
    sunlight = tuple(c * BREAK_LIGHT for c in _mix(SUN_GOLD, SUN_WHITE, _smooth(2, 20, sun_alt)))

    # Wind across the mantle (+ to the right) and toward you.
    heading = math.radians(obs["wind_dir"] + 180)
    right = math.radians(FACING + 90)
    across = obs["wind_speed"] * math.cos(heading - right)
    toward = obs["wind_speed"] * math.cos(heading - math.radians(FACING + 180))

    fog = 1 - _smooth(200, 5000, obs["visibility"])
    if code in (45, 48):
        fog = max(fog, 0.5)

    def place(alt, az):
        return 12 + 12 * _ahead(az) / VIEW, alt / 10

    return {
        "top": top, "bottom": bottom,
        "cloud": cloud, "cloud_color": cloud_color,
        "layers": (obs["cloud_low"] / 100, obs["cloud_high"] / 100),
        "breaks": breaks, "sunlight": sunlight,
        "stars": 1 - _smooth(-14, -6, sun_alt),
        "rain": rain, "snow": snow,
        "rain_color": _mix(RAIN_NIGHT, RAIN_DAY, day), "snow_color": _mix(SNOW_NIGHT, SNOW_DAY, day),
        "wind": (across, toward), "gust": obs["gust"] - obs["wind_speed"],
        "storm": 1 if storm else 0, "fog": fog, "temperature": obs["temperature"],
        "sun": place(sun_alt, sun_az) + (day,),
        "moon": place(moon_alt, moon_az) + (moon_lit if waxing else -moon_lit,),
    }


def _number(v):
    return f"{v:.2f}".rstrip("0").rstrip(".") if abs(v) >= 0.005 else "0"


def message(params):
    parts = []
    for key, value in params.items():
        values = value if isinstance(value, tuple) else (value,)
        parts.append(f"{key}=" + ",".join(_number(v) for v in values))
    return "#WX " + " ".join(parts)


# ============================================================
# MAIN LOOP
# ============================================================

def read_overrides():
    try:
        with open(OVERRIDE_FILE) as f:
            return {k: v for k, v in json.load(f).items() if k in INPUTS and v is not None}
    except (OSError, ValueError):
        return {}


def scene_time(overrides):
    now = datetime.now(timezone.utc)
    if "hour" in overrides:
        local = datetime.now().astimezone()
        h = float(overrides["hour"]) % 24
        local = local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=h)
        return local.astimezone(timezone.utc)
    return now


def write_json(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(value, f, indent=1)
    os.replace(tmp, path)


def main():
    data = None
    fetched = 0.0
    tried = 0.0
    error = None
    sent = 0.0
    listening = False          # the scene answered and hasn't stopped
    started = None             # (command, when) last seen
    asks = []                  # when to ask whether it's listening
    last_inputs = None

    def heard():
        try:
            return pico_ctrl.ask(QUESTION, ANSWER)
        except Exception as e:
            log.warning("ask failed: %s", e)
            return False

    while True:
        now = time.time()
        if now - tried >= (FETCH_EVERY_S if data else 60):
            tried = now
            try:
                data = fetch()
                fetched = now
                error = None
                log.info("fetched weather")
            except Exception as e:  # keep the last good data and retry
                error = f"{type(e).__name__}: {e}"
                log.warning("fetch failed: %s", error)

        overrides = read_overrides()
        when = scene_time(overrides)
        live = observe(data, datetime.now(timezone.utc)) if data else dict(CALM)
        if data and now - fetched > STALE_S:
            live = dict(CALM)
        inputs = {**live, **{k: float(v) for k, v in overrides.items() if k != "hour"}}
        if "cloud" in overrides:
            # An overall cover sets both layers unless they're given too.
            inputs["cloud_low"] = float(overrides.get("cloud_low", inputs["cloud"]))
            inputs["cloud_high"] = float(overrides.get("cloud_high", 0.6 * inputs["cloud"]))
        params = look(inputs, when)

        # Only send to the scene once it answers: anything else running
        # on the Pico (or a Pico that's restarted) wouldn't read the
        # lines, and unread input soon blocks the Pico entirely. So a
        # few short questions after each scene command, and one before
        # each send; no answer, no more until the next scene command.
        command = pico_ctrl.last_command()
        if command != started:
            started = command
            listening = False
            asks = [now + s for s in ASK_AFTER_S] if command[0] == SCENE_CMD else []
        if asks and now >= asks[0]:
            asks.pop(0)
            if heard():
                listening = True
                asks = []
                sent = 0.0
                log.info("Live Weather is listening")
        changed = (inputs, overrides.get("hour")) != last_inputs
        if listening and (changed or now - sent >= SEND_EVERY_S):
            if heard():
                try:
                    pico_ctrl.send_line(message(params))
                    sent = now
                except Exception as e:
                    log.warning("send failed: %s", e)
            else:
                listening = False
                log.info("Live Weather stopped answering")
        last_inputs = (inputs, overrides.get("hour"))

        write_json(STATE_FILE, {
            "updated": datetime.now().astimezone().isoformat(timespec="seconds"),
            "fetched": datetime.fromtimestamp(fetched).astimezone().isoformat(timespec="seconds") if fetched else None,
            "error": error, "active": listening,
            "live": live, "overrides": overrides, "inputs": inputs,
            "scene_time": when.astimezone().isoformat(timespec="minutes"),
            "look": params,
        })
        time.sleep(1)


if __name__ == "__main__":
    main()
