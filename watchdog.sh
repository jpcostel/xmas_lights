MODE_FILE="/tmp/current_led_mode"
PID_FILE="/tmp/main_py_pid"

SCRIPT_DIR = `pwd`

while true; do
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            sleep 30
            continue
        fi
    else 
        PID=`pgrep main.py`
        echo 
    fi

    # process dead — relaunch with saved mode
    MODE=$(cat "$MODE_FILE")

    case "$MODE" in
        twinkle) FLAG="--twinkle" ;;
        pulse) FLAG="--pulse" ;;
        xmas) FLAG="--xmas" ;;
        xmas_twinkle) FLAG="--xmas_twinkle" ;;
        *) FLAG="--twinkle" ;;
    esac

    echo "Restarting main.py with mode $FLAG"
    sudo $SCRIPT_DIR/.venv/bin/python3 $SCRIPT_DIR/main.py $FLAG &
    echo $! > $PID_FILE

    sleep 30
done
