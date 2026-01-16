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

        <form method="post" action="/snow_colors">
            <button style="font-size:20px">❄ Snow Xmas-Colors</button>
        </form>

        <form method="post" action="/twinkle">
            <button style="font-size:20px">✨ Twinkle</button>
        </form>

        <form method="post" action="/ripple">
            <button style="font-size:20px">✨ Twinkle with Ripples</button>
        </form>

        <form method="post" action="/gold_twinkle">
            <button style="font-size:20px">✨ Gold Stars</button>
        </form>

        <form method="post" action="/gold_ripple">
            <button style="font-size:20px">✨ Dynamic Gold Stars</button>
        </form>

        <form method="post" action="/cool_twinkle">
            <button style="font-size:20px">✨ Cool Stars</button>
        </form>

        <form method="post" action="/cool_ripple">
            <button style="font-size:20px">✨ Wavy Cool Stars</button>
        </form>                

        <form method="post" action="/warm_twinkle">
            <button style="font-size:20px">✨ Hot Stars</button>
        </form>

        <form method="post" action="/warm_ripple">
            <button style="font-size:20px">✨ Explosive Hot Stars</button>
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

@app.route("/snow_colors", methods=["POST"])
def snow_colors():
    global CURRENT_MODE
    pico_ctrl.interrupt()
    pico_ctrl.run("snow.snowfall_effect(strips, True)")
    CURRENT_MODE = "snow.snowfall_effect(strips, True)"
    return redirect(url_for("index"))

@app.route("/xmas_ripple", methods=["POST"])
def ripple():
    global CURRENT_MODE
    pico_ctrl.interrupt()
    pico_ctrl.run("stars.starfield(strips)")
    CURRENT_MODE = "stars.starfield(strips)"
    return redirect(url_for("index"))

@app.route("/xmas_twinkle", methods=["POST"])
def twinkle():
    global CURRENT_MODE
    pico_ctrl.interrupt()
    pico_ctrl.run("stars.starfield(strips, ripples_on=False)")
    CURRENT_MODE = "stars.starfield(strips, ripples_on=False)"
    return redirect(url_for("index"))

@app.route("/cool_ripple", methods=["POST"])
def cool_ripple():
    global CURRENT_MODE
    pico_ctrl.interrupt()
    pico_ctrl.run("stars.starfield(strips, 1, 2)")
    CURRENT_MODE = "stars.starfield(strips, 1, 2)"
    return redirect(url_for("index"))

@app.route("/cool_twinkle", methods=["POST"])
def cool_twinkle():
    global CURRENT_MODE
    pico_ctrl.interrupt()
    pico_ctrl.run("stars.starfield(strips, 0, 2)")
    CURRENT_MODE = "stars.starfield(strips, 0, 2)"
    return redirect(url_for("index"))

@app.route("/warm_ripple", methods=["POST"])
def warm_ripple():
    global CURRENT_MODE
    pico_ctrl.interrupt()
    pico_ctrl.run("stars.starfield(strips, 1, 3)")
    CURRENT_MODE = "stars.starfield(strips, 1, 3)"
    return redirect(url_for("index"))

@app.route("/warm_twinkle", methods=["POST"])
def warm_twinkle():
    global CURRENT_MODE
    pico_ctrl.interrupt()
    pico_ctrl.run("stars.starfield(strips, 0, 3)")
    CURRENT_MODE = "stars.starfield(strips, 0, 3)"
    return redirect(url_for("index"))

@app.route("/gold_ripple", methods=["POST"])
def gold_ripple():
    global CURRENT_MODE
    pico_ctrl.interrupt()
    pico_ctrl.run("stars.starfield(strips, 1, 1)")
    CURRENT_MODE = "stars.starfield(strips, 1, 1)"
    return redirect(url_for("index"))

@app.route("/gold_twinkle", methods=["POST"])
def gold_twinkle():
    global CURRENT_MODE
    pico_ctrl.interrupt()
    pico_ctrl.run("stars.starfield(strips, 0, 1)")
    CURRENT_MODE = "stars.starfield(strips, 0, 1)"
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
