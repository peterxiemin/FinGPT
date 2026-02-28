#!/bin/bash
# Check the status of APScheduler daemon

APP_DIR="/root/FinGPT/fingpt/FinGPT_Forecaster"
PID_FILE="$APP_DIR/.scheduler.pid"

echo "=================================="
echo "APScheduler Daemon Status"
echo "=================================="

if [ ! -f "$PID_FILE" ]; then
    echo "❌ Status: NOT RUNNING (no PID file)"
    echo ""
    echo "To start: bash start_scheduler.sh"
    exit 1
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    echo "✅ Status: RUNNING"
    echo "📊 PID: $PID"
    echo ""
    echo "Process info:"
    ps aux | grep $PID | grep -v grep
    echo ""
    echo "Recent logs:"
    tail -20 "$APP_DIR/scheduler.log"
else
    echo "❌ Status: STOPPED (PID file exists but process not found)"
    echo "📊 Stale PID: $PID"
    echo ""
    echo "Cleaning up stale PID file..."
    rm "$PID_FILE"
    echo "✅ Cleaned. To restart: bash start_scheduler.sh"
fi

echo ""
echo "=================================="
echo "Pipeline logs:"
tail -10 "$APP_DIR/cron_pipeline.log"
