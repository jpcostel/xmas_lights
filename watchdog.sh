#!/bin/bash

# Path to your project
SCRIPT_DIR=`pwd`
SCRIPT="$SCRIPT_DIR/main.py"

# Log file
LOGFILE="$SCRIPT_DIR/watchdog.log"

# How often to check (seconds)
INTERVAL=30

echo "$(date '+%Y-%m-%d %H:%M:%S')  Watchdog started." >> "$LOGFILE"

while true; do
    # Look for a running instance of main.py
    PID=$(pgrep -f "$SCRIPT")

    if [ -z "$PID" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S')  main.py not running. Restarting..." >> "$LOGFILE"
        
        # Start script in background
        sudo ./venv/bin/python3 "$SCRIPT" >> "$LOGFILE" 2>&1 &
    fi

    sleep "$INTERVAL"
done
