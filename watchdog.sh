MODE_FILE="/tmp/current_led_mode"
PID_FILE="/tmp/webserver_pid"
LOG="/tmp/webserver.log"

SCRIPT_DIR=`pwd`
PYTHON=`pwd`/.venv/bin/python3

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
    nohup sudo $PYTHON $SCRIPT_DIR/webserver.py $LOG 2>&1 &
    echo $! > $PID_FILE

    sleep 30
done
