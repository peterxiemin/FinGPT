# Python 定时任务调度模板

这是从 FinGPT Forecaster 项目沉淀出来的通用模板，可用于快速部署定时任务。

## 快速决策树

```
需要定时执行任务吗？
│
├─ 是否在传统 Linux 服务器？
│  ├─ 是 → 检查是否有 cron 或 systemd
│  │  ├─ 有 cron → 方案1: 使用 cron (推荐)
│  │  ├─ 有 systemd → 方案2: 使用 systemd timer (现代)
│  │  └─ 都没有 → 方案3: APScheduler
│  │
│  └─ 否 (Docker/容器/特殊环境) → 方案3: APScheduler (推荐)
```

---

## 方案 1: Cron (传统 Linux)

### 优点
- ✅ 系统原生
- ✅ 轻量级
- ✅ 广泛支持

### 缺点
- ❌ 只在 Linux 上
- ❌ 修改需要编辑文件

### 部署步骤

```bash
# 1. 创建脚本 my_task.sh
#!/bin/bash
cd /path/to/project
python my_script.py --arg1 value1

# 2. 添加 crontab
crontab -e

# 3. 在编辑器中添加一行
0 2 * * 0   /path/to/my_task.sh

# 4. 验证
crontab -l
```

### Cron 时间表格式
```
分 时 日 月 周  命令
0  2  *  *  0   /path/to/script.sh
│  │  │  │  │
│  │  │  │  └─ 周 (0=Sunday, 6=Saturday)
│  │  │  └──── 月 (1-12)
│  │  └─────── 日 (1-31)
│  └────────── 时 (0-23)
└──────────── 分 (0-59)

示例:
每周日凌晨2点: 0 2 * * 0
每天凌晨2点: 0 2 * * *
每小时执行: 0 * * * *
```

---

## 方案 2: systemd timer (现代 Linux)

### 优点
- ✅ 现代方案
- ✅ 系统集成
- ✅ 功能强大

### 缺点
- ❌ 需要 systemd init
- ❌ 配置略复杂

### 部署步骤

```bash
# 1. 创建服务文件 /etc/systemd/system/my-task.service
[Unit]
Description=My Task
After=network.target

[Service]
Type=oneshot
ExecStart=/path/to/my_task.sh
User=root

[Install]
WantedBy=multi-user.target

# 2. 创建定时器 /etc/systemd/system/my-task.timer
[Unit]
Description=My Task Timer
Requires=my-task.service

[Timer]
OnCalendar=Sun *-*-* 02:00:00  # 每周日凌晨2点

[Install]
WantedBy=timers.target

# 3. 启用并启动
sudo systemctl daemon-reload
sudo systemctl enable my-task.timer
sudo systemctl start my-task.timer

# 4. 验证
sudo systemctl list-timers
```

### OnCalendar 时间表格式
```
Mon *-*-* 00:00:00   每周一凌晨
Sun *-*-* 02:00:00   每周日凌晨2点
*-*-01 00:00:00      每月1号
*-*-* 02,14:00:00    每天凌晨2点和下午2点
```

---

## 方案 3: APScheduler (推荐用于特殊环境)

### 优点
- ✅ 无系统依赖
- ✅ 跨平台 (Linux/Mac/Windows)
- ✅ Python 原生
- ✅ 容器友好
- ✅ 易于修改参数

### 缺点
- ❌ 占用内存 (~25 MB)
- ❌ 常驻进程

### 快速部署

#### 1. 安装依赖
```bash
pip install APScheduler
```

#### 2. 创建 daemon 脚本 (scheduler_daemon.py)
```python
import subprocess
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("scheduler.log"), logging.StreamHandler()]
)
logger = logging.getLogger("Scheduler")

def my_task():
    """执行的任务"""
    logger.info(f"Task started at {datetime.now()}")
    result = subprocess.run(["python", "my_script.py", "--arg1", "value1"])
    logger.info(f"Task completed with code {result.returncode}")

def start_scheduler():
    scheduler = BackgroundScheduler(
        job_defaults={'coalesce': True, 'max_instances': 1}
    )

    # 每周日 02:00 运行
    scheduler.add_job(
        my_task,
        CronTrigger(day_of_week=6, hour=2, minute=0),
        id="my_task",
        name="My Task"
    )

    scheduler.start()
    logger.info("Scheduler started")

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()

if __name__ == "__main__":
    start_scheduler()
```

#### 3. 创建启动脚本 (start_scheduler.sh)
```bash
#!/bin/bash
APP_DIR="/path/to/project"
PYTHON_BIN="/path/to/python"  # 虚拟环境的python
PID_FILE="$APP_DIR/.scheduler.pid"

cd "$APP_DIR"
nohup "$PYTHON_BIN" scheduler_daemon.py > scheduler.log 2>&1 &
echo $! > "$PID_FILE"
echo "✅ Scheduler started (PID: $(cat $PID_FILE))"
```

#### 4. 启动
```bash
bash start_scheduler.sh
```

### APScheduler CronTrigger 对应表

```python
# Cron 时间表 → APScheduler 参数

# 0 2 * * 0 (每周日凌晨2点)
CronTrigger(day_of_week=6, hour=2, minute=0)

# 0 2 * * * (每天凌晨2点)
CronTrigger(hour=2, minute=0)

# 0 * * * * (每小时)
CronTrigger(minute=0)

# day_of_week 参数: 0=Monday, 1=Tuesday, ..., 6=Sunday
# hour 参数: 0-23 (UTC)
# minute 参数: 0-59
```

---

## 监控和调试

### 查看日志
```bash
# Cron
grep CRON /var/log/syslog  # 或 /var/log/cron

# systemd timer
sudo journalctl -u my-task.service -f

# APScheduler
tail -f scheduler.log
```

### 手动测试
```bash
# 直接运行脚本测试
python my_script.py --arg1 value1

# 验证是否成功
echo $?  # 0 表示成功
```

### 故障排查
```bash
# Cron: 检查是否创建了任务
crontab -l

# systemd: 检查 timer 状态
sudo systemctl status my-task.timer

# APScheduler: 检查进程
ps aux | grep scheduler_daemon.py
```

---

## 选择建议

| 场景 | 推荐方案 |
|------|--------|
| 传统 Linux 服务器，有 cron | Cron |
| Ubuntu 18+，现代 Linux | systemd timer |
| Docker 容器 | APScheduler |
| 需要动态修改参数 | APScheduler |
| 跨平台 (Windows/Mac/Linux) | APScheduler |
| 资源受限 | Cron 或 systemd timer |

---

## 参考实现

完整的实现参考: `/root/FinGPT/fingpt/FinGPT_Forecaster/`

文件清单:
- `apscheduler_daemon.py` - 完整的 APScheduler 实现
- `start_scheduler.sh` - 启动脚本
- `stop_scheduler.sh` - 停止脚本
- `check_scheduler.sh` - 状态检查脚本
- `APSCHEDULER_SETUP.md` - 详细配置指南

---

**版本**: 1.0
**创建日期**: 2026-02-28
**来源项目**: FinGPT Forecaster
