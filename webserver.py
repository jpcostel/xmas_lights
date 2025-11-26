#!/home/jpcostel/Projects/xmas_lights/.venv/bin/python3

from flask import Flask, render_template, redirect, url_for
import subprocess
import os
import signal
import time

app = Flask(__name__)

MODE_FILE = "/tmp/current_led_mode"
PID_FILE = "/tmp/main_py_pid"


def write_mode(mode):
    """Write mode to MODE_FILE for watchdog + UI."""
    with open(MODE_FILE, "w") as f:
        f.write(mode)


def get_current_mode():
    if os.path.exists(MODE_FILE):
        return open(MODE_FILE).read().strip()
    return "unknown"


def get_running_pid():
    """Return PID of main.py if PID_FILE exists and pid alive."""
    if not os.path.exists(PID_FILE):
        return None

    try:
        pid = int(open(PID_FILE).read().strip())
        os.kill(pid, 0)  # probe process
        return pid
    except:
        return None


def kill_main_py():
    pid = get_running_pid()
    if pid:
        try:
            print(f"Killing main.py (PID={pid})")
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
        except Exception as e:
            print(f"Error killing main.py: {e}")


def launch_main_py(mode):
    """Launch main.py with the correct --mode argument and store PID."""

    arg_map = {
        "twinkle": "--twinkle",
        "pulse": "--pulse",
        "xmas": "--xmas",
        "xmas_twinkle": "--xmas_twinkle",
    }

    flag = arg_map[mode]

    print(f"Launching main.py {flag}")

    # Launch detached background process
    p = subprocess.Popen(
        ["sudo", "/home/jpcostel/Projects/xmas_lights/.venv/bin/python3", "/home/jpcostel/Projects/xmas_lights/main.py", flag],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    with open(PID_FILE, "w") as f:
        f.write(str(p.pid))


@app.route("/")
def index():
    mode = get_current_mode()
    return render_template("index.html", mode=mode)


@app.route("/set/<mode>")
def set_mode(mode):
    # 1. Save mode for watchdog
    write_mode(mode)

    # 2. Kill running main.py
    kill_main_py()

    # 3. Launch new main.py with correct argument
    launch_main_py(mode)

    # 4. Load updated UI
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Bind to all interfaces so your phone can access it
    app.run(host="0.0.0.0", port=5000)
