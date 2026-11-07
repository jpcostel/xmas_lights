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
# The last command run, so the weather service knows when its scene
# may be on.
LAST_FILE = os.path.join(HERE, ".pico_last_command")


def send_raw(cmd: bytes):
    with open(LOCK_FILE, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        # write_timeout: a Pico that's stopped taking input mustn't hang
        # every caller on the lock.
        with serial.Serial(PORT, BAUD, timeout=1, write_timeout=3) as ser:
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
    """Send a line to whatever's running, without interrupting it.

    Only send to something that reads its input (check with ask()): the
    Pico holds unread input, and once a few hundred bytes have piled up
    it takes nothing more, not even the Ctrl-C to stop a scene.
    """
    send_raw((line + "\r\n").encode("utf-8"))


def ask(question: str, answer: str, wait: float = 1.0) -> bool:
    """Send a short line to whatever's running and see whether it
    replies with the answer line within wait seconds."""
    with open(LOCK_FILE, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with serial.Serial(PORT, BAUD, timeout=0.1, write_timeout=3) as ser:
            time.sleep(0.2)  # allow port settle
            ser.reset_input_buffer()
            ser.write((question + "\r\n").encode("utf-8"))
            ser.flush()
            heard = b""
            end = time.time() + wait
            while time.time() < end:
                heard += ser.read(256)
                if answer.encode("utf-8") in heard.splitlines():
                    return True
    return False


def last_command():
    """The last command run and when, as (text, mtime)."""
    try:
        with open(LAST_FILE) as f:
            return f.read(), os.fstat(f.fileno()).st_mtime
    except OSError:
        return "", 0.0
