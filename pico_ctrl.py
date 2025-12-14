# pico_ctrl.py
import serial
import time

PORT = "/dev/ttyACM0"
BAUD = 115200

def send_raw(cmd: bytes):
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
    send_raw((cmd + "\n").encode("utf-8"))
    send_raw(("\n").encode("utf-8"))
    