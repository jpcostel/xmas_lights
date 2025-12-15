# webserver.py
from flask import Flask, request, redirect, url_for
import pico_ctrl
import time

app = Flask(__name__)

CURRENT_MODE = "snowfall_effect(strips)"

@app.route("/", methods=["GET"])
def index():
    return f"""
    <html>
    <body style="font-family:sans-serif">
        <h2>LED Control</h2>

        <form method="post" action="/snow">
            <button style="font-size:20px">❄ Snow</button>
        </form>

        <form method="post" action="/twinkle">
            <button style="font-size:20px">✨ Twinkle</button>
        </form>

        <form method="post" action="/scroll">
            <input name="text" placeholder="Scroll text">
            <button style="font-size:20px">📝 Scroll</button>
        </form>

        <p>Current mode: <b>{CURRENT_MODE}</b></p>
    </body>
    </html>
    """

@app.route("/snow", methods=["POST"])
def snow():
    global CURRENT_MODE
    pico_ctrl.interrupt()
    pico_ctrl.run("snow.snowfall_effect(strips)")
    CURRENT_MODE = "snow.snowfall_effect(strips)"
    return redirect(url_for("index"))

@app.route("/twinkle", methods=["POST"])
def twinkle():
    global CURRENT_MODE
    pico_ctrl.interrupt()
    pico_ctrl.run("effects.twinkle_stars(strips)")
    CURRENT_MODE = "effects.twinkle_stars(strips)"
    return redirect(url_for("index"))

@app.route("/scroll", methods=["POST"])
def scroll():
    global CURRENT_MODE

    text = request.form.get("text", "").replace('"', '')

    # Stop current animation
    pico_ctrl.interrupt()

    # Run scroll text (blocking on Pico)
    pico_ctrl.run(
        f'scroll.scroll_text(strips, "{text.upper()}", (255,32,32), (10, 30, 10), 0.03)'
    )

    # Give the scroll time to start
    time.sleep(0.2)

    # Resume previous mode
    pico_ctrl.run(CURRENT_MODE)

    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
