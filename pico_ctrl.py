# pico_ctrl.py
import fcntl
import os
import serial
import time

PORT = "/dev/ttyACM0"
BAUD = 115200

HERE = os.path.dirname(os.path.abspath(__file__))
# The web server, HomeKit bridge and weather service all write to the
# Pico; this lock keeps their writes from interleaving.
LOCK_FILE = os.path.join(HERE, ".pico_lock")
# The last command run, so the weather service knows when its scene is on.
LAST_FILE = os.path.join(HERE, ".pico_last_command")


def send_raw(cmd: bytes):
    with open(LOCK_FILE, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with serial.Serial(PORT, BAUD, timeout=1) as ser:
            time.sleep(0.2)  # allow port settle
            ser.write(cmd)
            ser.flush()

def interrupt():
    # Ctrl-C twice to be safe
    send_raw(b"\x03")
    time.sleep(0.1)
    send_raw(b"\x03")
    time.sleep(0.2)

def run(cmd: str):
    send_raw((cmd + "\r\n").encode("utf-8"))
    try:
        with open(LAST_FILE, "w") as f:
            f.write(cmd)
    except OSError:
        pass


def send_line(line: str):
    """Send a line to whatever's running, without interrupting it."""
    send_raw((line + "\r\n").encode("utf-8"))


def last_command():
    try:
        with open(LAST_FILE) as f:
            return f.read()
    except OSError:
        return ""
