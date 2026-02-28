#!/bin/bash

# 配置路径
APP_DIR="/root/FinGPT/fingpt/FinGPT_Forecaster"
PYTHON_BIN="/usr/local/miniconda3/envs/fingpt/bin/python"
LOG_FILE="$APP_DIR/app.log"

cd $APP_DIR

case "$1" in
    start)
        echo "正在启动 FinGPT Forecaster..."
        # Load all variables from .env uniformly
        set -a; source .env; set +a
        export HF_ENDPOINT=https://hf-mirror.com

        # 启动程序并重定向日志
        nohup $PYTHON_BIN -u app.py > $LOG_FILE 2>&1 &
        echo "服务已在后台启动。进程 ID: $!"
        echo "你可以运行 './manage.sh logs' 查看启动进度。"
        ;;
    stop)
        echo "正在停止 FinGPT Forecaster..."
        pkill -9 -f "python -u app.py"
        echo "服务已停止。"
        ;;
    restart)
        bash "$0" stop
        sleep 2
        bash "$0" start
        ;;
    status)
        PID=$(pgrep -f "python -u app.py")
        if [ -z "$PID" ]; then
            echo "服务状态: 未运行"
        else
            echo "服务状态: 正在运行 (PID: $PID)"
            nvidia-smi | grep "python"
        fi
        ;;
    logs)
        echo "正在实时查看日志 (按下 Ctrl+C 退出)..."
        tail -f $LOG_FILE
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs}"
        exit 1
esac
