# webserver.py
from flask import Flask, request, redirect, url_for
import pico_ctrl
import time

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
