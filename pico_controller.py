import sys
import time
import select
from wiring import * 
import snow
import effects
import scroll

# Current mode
current_mode = "SNOW"
current_text = "HELLO"

def read_serial_nonblocking():
    """Read one line from USB serial if available."""
    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)

    if poller.poll(0):
        line = sys.stdin.readline().strip()
        return line
    return None


def handle_command(cmd):
    global current_mode, current_text

    print("CMD:", cmd)

    if cmd == "SNOW":
        current_mode = "SNOW"

    elif cmd.startswith("TEXT:"):
        current_mode = "TEXT"
        current_text = cmd[5:]

    elif cmd == "OFF":
        current_mode = "OFF"


# -----------------------
# Main loop
# -----------------------

while True:
    cmd = read_serial_nonblocking()
    if cmd:
        handle_command(cmd)

        if current_mode == "SNOW":
            snow.snowfall_effect(strips)
        
    # Your existing LED update logic goes here
    # Example:
    # if current_mode == "SNOW":
    #     snowfall_step()
    # elif current_mode == "TEXT":
    #     scroll_text_step(current_text)
    # elif current_mode == "OFF":
    #     clear()


    time.sleep(0.02)
