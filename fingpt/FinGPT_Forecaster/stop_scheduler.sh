#!/bin/bash
# Stop the APScheduler daemon

APP_DIR="/root/FinGPT/fingpt/FinGPT_Forecaster"
PID_FILE="$APP_DIR/.scheduler.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "❌ Scheduler is not running (no PID file found)"
    exit 1
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    echo "🛑 Stopping scheduler (PID: $PID)..."
    kill "$PID"
    sleep 2

    if kill -0 "$PID" 2>/dev/null; then
        echo "⚠️  Process still running, forcing termination..."
        kill -9 "$PID"
    fi

    rm "$PID_FILE"
    echo "✅ Scheduler stopped"
else
    echo "❌ Scheduler process not found (PID: $PID)"
    rm "$PID_FILE"
fi
