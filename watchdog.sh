MODE_FILE="/tmp/current_led_mode"
PID_FILE="/tmp/webserver_pid"

SCRIPT_DIR = `pwd`

while true; do
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            sleep 30
            continue
        fi
    else 
        PID=`pgrep webserver.py`
        echo $PID > $PID_FILE
    fi

    # process dead — relaunch
    echo "Restarting webserver"
    sudo $SCRIPT_DIR/.venv/bin/python3 $SCRIPT_DIR/webserver.py &
    echo $! > $PID_FILE

    sleep 30
done
