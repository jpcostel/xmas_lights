from flask import Flask, render_template, redirect, url_for
import subprocess
import os

app = Flask(__name__)

# CURRENT_MODE_FILE = "/tmp/current_led_mode"


def set_mode(mode_name):
    """kill main.py and relaunch with the new mode"""
    with open(CURRENT_MODE_FILE, "w") as f:
        f.write(mode_name)


@app.route("/")
def index():
    # Always read current mode to show state
    mode = "unknown"
    if os.path.exists(CURRENT_MODE_FILE):
        mode = open(CURRENT_MODE_FILE).read().strip()
    return render_template("index.html", mode=mode)


@app.route("/set/<mode>")
def set_mode_route(mode):
    set_mode(mode)
    return redirect(url_for('index'))


if __name__ == "__main__":
    # Host on all interfaces so your phone can reach it
    app.run(host="0.0.0.0", port=5000)
