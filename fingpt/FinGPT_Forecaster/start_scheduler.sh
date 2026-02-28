#!/bin/bash
# Start the APScheduler daemon in the background

APP_DIR="/root/FinGPT/fingpt/FinGPT_Forecaster"
PYTHON_BIN="/usr/local/miniconda3/envs/fingpt/bin/python"
PID_FILE="$APP_DIR/.scheduler.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "❌ Scheduler is already running (PID: $OLD_PID)"
        exit 1
    fi
fi

# Start in background
cd "$APP_DIR"
nohup "$PYTHON_BIN" apscheduler_daemon.py > scheduler.log 2>&1 &
NEW_PID=$!

# Save PID
echo "$NEW_PID" > "$PID_FILE"

echo "✅ Scheduler started (PID: $NEW_PID)"
echo "📝 Log file: $APP_DIR/scheduler.log"
echo "💡 To check status: ps aux | grep apscheduler_daemon.py"
echo "💡 To stop: kill $NEW_PID"
