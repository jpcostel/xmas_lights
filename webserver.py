# webserver.py
from flask import Flask, request, redirect, url_for
import html
import json
import os
import pico_ctrl
import time

import weather_service

from scenes import SCENES, DEFAULT_SCENE

app = Flask(__name__)

CURRENT_MODE = SCENES[DEFAULT_SCENE]["cmd"]


def run_scene(key):
    global CURRENT_MODE
    cmd = SCENES[key]["cmd"]
    pico_ctrl.interrupt()
    pico_ctrl.run(cmd)
    CURRENT_MODE = cmd


@app.route("/", methods=["GET"])
def index():
    buttons = "\n".join(
        f'''<form method="post" action="/scene/{key}">
            <button style="font-size:20px">{scene["web_label"]}</button>
        </form>'''
        for key, scene in SCENES.items()
    )
    return f"""
    <html>
    <body style="font-family:sans-serif">
        <h2>LED Control</h2>

        {buttons}

        <form method="post" action="/scroll">
            <input name="text" placeholder="Scroll text">
            <button style="font-size:20px">📝 Scroll</button>
        </form>

        <p>Current mode: <b>{CURRENT_MODE}</b></p>
        <p><a href="/weather">🌦️ Weather details and preview</a></p>
    </body>
    </html>
    """


@app.route("/scene/<key>", methods=["POST"])
def scene(key):
    if key not in SCENES:
        return "Unknown scene", 404
    run_scene(key)
    return redirect(url_for("index"))


@app.route("/scroll", methods=["POST"])
def scroll():
    global CURRENT_MODE

    text = request.form.get("text", "").replace('"', '')

    # Stop current animation
    pico_ctrl.interrupt()

    # Run scroll text (blocking on Pico)
    pico_ctrl.run(
        f'scroll.scroll_text(strips, "{text.upper()}", (16, 255, 16), (0,0,0), 0.03)'
    )

    # Give the scroll time to start
    time.sleep(0.2)

    # Resume previous mode
    pico_ctrl.run(CURRENT_MODE)

    return redirect(url_for("index"))


# Quick previews: overrides to try on the Live Weather scene.
WEATHER_PRESETS = {
    "Clear night": {"cloud": 0, "rain": 0, "snow": 0, "hour": 22},
    "Sunrise": {"cloud": 30, "rain": 0, "snow": 0, "hour": 7.3},
    "Partly cloudy noon": {"cloud": 50, "rain": 0, "snow": 0, "hour": 12},
    "Drizzle": {"cloud": 100, "rain": 0.4, "snow": 0, "code": 51},
    "Heavy rain": {"cloud": 100, "rain": 10, "snow": 0, "code": 65},
    "Thunderstorm": {"cloud": 100, "rain": 15, "snow": 0, "code": 95, "wind_speed": 8},
    "Gentle snow": {"cloud": 100, "rain": 0, "snow": 0.8, "code": 73, "wind_speed": 1},
    "Blizzard": {"cloud": 100, "rain": 0, "snow": 4, "code": 75, "wind_speed": 13, "gust": 20},
}


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _show(v):
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    if isinstance(v, list):
        return ", ".join(_show(x) for x in v)
    return html.escape(str(v))


@app.route("/weather", methods=["GET"])
def weather_page():
    state = _read_json(weather_service.STATE_FILE)
    overrides = _read_json(weather_service.OVERRIDE_FILE)
    live = state.get("live", {})
    rows = "\n".join(
        f"""<tr><td>{key}</td><td>{_show(live.get(key, ""))}</td><td>{unit}</td>
            <td><input name="{key}" value="{_show(overrides.get(key, ""))}" size="6"></td></tr>"""
        for key, unit in weather_service.INPUTS.items()
    )
    presets = "\n".join(
        f"""<button name="preset" value="{html.escape(name)}">{html.escape(name)}</button>"""
        for name in WEATHER_PRESETS
    )
    look = "\n".join(f"<tr><td>{k}</td><td>{_show(v)}</td></tr>" for k, v in state.get("look", {}).items())
    status = "running" if state.get("active") else "not running"
    if not state:
        status = "no state yet: is weather_service running?"
    return f"""
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body style="font-family:sans-serif">
        <h2>Live Weather</h2>
        <p><a href="/">← LED Control</a></p>
        <p>Scene: <b>{status}</b><br>
           Weather fetched: {_show(state.get("fetched"))}<br>
           Scene time: {_show(state.get("scene_time"))}<br>
           {"<b>Fetch error:</b> " + _show(state["error"]) if state.get("error") else ""}</p>

        <form method="post" action="/weather">
            <p>Preview: {presets}</p>
            <table>
                <tr><th>input</th><th>live</th><th></th><th>override</th></tr>
                {rows}
            </table>
            <p>Blank means live. <button>Save overrides</button>
               <button name="clear" value="1">Back to live</button></p>
        </form>

        <h3>What the scene is told</h3>
        <table>{look}</table>
    </body>
    </html>
    """


@app.route("/weather", methods=["POST"])
def weather_save():
    if request.form.get("clear"):
        overrides = {}
    elif request.form.get("preset") in WEATHER_PRESETS:
        overrides = dict(WEATHER_PRESETS[request.form["preset"]])
    else:
        overrides = {}
        for key in weather_service.INPUTS:
            value = request.form.get(key, "").strip()
            if value:
                try:
                    overrides[key] = float(value)
                except ValueError:
                    pass
    weather_service.write_json(weather_service.OVERRIDE_FILE, overrides)
    return redirect(url_for("weather_page"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
