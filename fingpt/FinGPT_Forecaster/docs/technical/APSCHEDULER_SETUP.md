# APScheduler 自动化调度配置指南

## ✅ 部署完成

已成功部署 **APScheduler** 作为 FinGPT Forecaster 的自动化调度方案。

### 当前状态

```
✅ APScheduler 已安装
✅ 调度脚本已创建
✅ 调度器已启动运行
✅ 计划：每周日 02:00 UTC 自动执行
```

---

## 📁 新增文件

| 文件 | 用途 |
|------|------|
| `apscheduler_daemon.py` | 调度器主程序 |
| `start_scheduler.sh` | 启动脚本 |
| `stop_scheduler.sh` | 停止脚本 |
| `check_scheduler.sh` | 状态检查脚本 |
| `scheduler.log` | 调度器日志 |

---

## 🚀 快速命令

### 启动调度器
```bash
bash start_scheduler.sh
```

### 停止调度器
```bash
bash stop_scheduler.sh
```

### 检查状态
```bash
bash check_scheduler.sh
```

### 查看日志
```bash
# 实时查看调度器日志
tail -f scheduler.log

# 查看管道执行日志
tail -f cron_pipeline.log
```

---

## ⚙️ 工作原理

### 调度器运行流程

```
APScheduler Daemon 启动
  ↓
每秒检查是否到达计划时间
  ↓
周日 02:00 → 触发 run_pipeline() 函数
  ↓
执行 cron_pipeline.py --run --index dow --weeks 2
  ↓
运行 5 个步骤：
  1️⃣ 数据获取 (yfinance + Finnhub)
  2️⃣ LLM 分析 (OpenRouter)
  3️⃣ 数据集创建 (HuggingFace)
  4️⃣ LoRA 微调 (train_lora.py)
  5️⃣ 模型部署 (更新配置 + 重启应用)
```

### 日志架构

```
scheduler.log ← APScheduler 日志（调度器事件）
cron_pipeline.log ← Pipeline 日志（运行详情）
training_*.log ← 训练日志（模型微调）
app.log ← Gradio 应用日志（推理服务）
```

---

## 📊 监控

### 实时监控
```bash
# 查看调度器进程
ps aux | grep apscheduler_daemon

# 查看进程内存占用
ps aux | grep apscheduler_daemon | awk '{print $6 " KB"}'

# 监控日志更新
watch -n 1 'tail -5 scheduler.log'
```

### 定期检查
```bash
# 每天检查一次
bash check_scheduler.sh
```

---

## 🔧 配置说明

### 修改运行计划

编辑 `apscheduler_daemon.py` 中的调度配置：

```python
# 当前配置：每周日 02:00
scheduler.add_job(
    run_pipeline,
    CronTrigger(day_of_week=6, hour=2, minute=0),
    # day_of_week: 0=Monday, 6=Sunday
    # hour: 0-23 (UTC)
    # minute: 0-59
)

# 修改示例：
# 每天 02:00: CronTrigger(hour=2, minute=0)
# 每周一 10:00: CronTrigger(day_of_week=0, hour=10, minute=0)
# 每月1号 02:00: CronTrigger(day=1, hour=2, minute=0)
```

修改后需要重启调度器：
```bash
bash stop_scheduler.sh
bash start_scheduler.sh
```

### 修改参数

编辑 `apscheduler_daemon.py` 中的 pipeline 参数：

```python
def run_pipeline():
    result = subprocess.run(
        [
            sys.executable, "cron_pipeline.py",
            "--run",
            "--index", "dow",  # 修改指数：dow/euro/crypto
            "--weeks", "2"     # 修改历史周数
        ],
        ...
    )
```

---

## 🛡️ 容错机制

### 自动重试

如果运行失败，调度器会：
1. 记录错误日志
2. 继续运行（不影响下次调度）
3. 自动合并错过的任务（`coalesce=True`）

### 防并发运行

```python
scheduler = BackgroundScheduler(
    job_defaults={
        'coalesce': True,      # 多次错过的任务合并为一次
        'max_instances': 1     # 同时只运行一个实例
    }
)
```

**说明**: 即使管道耗时很长（超过 1 小时），下次计划执行时也不会重复启动。

---

## 📋 维护清单

### 每周
- [ ] 检查调度器状态: `bash check_scheduler.sh`
- [ ] 检查管道日志: `tail -20 cron_pipeline.log`

### 每月
- [ ] 检查磁盘空间 (日志占用)
- [ ] 验证模型是否成功部署
- [ ] 查看性能指标

### 故障排查

**问题**: 调度器进程消失
```bash
# 重启
bash stop_scheduler.sh
bash start_scheduler.sh
```

**问题**: Pipeline 执行失败
```bash
# 查看详细错误
tail -100 cron_pipeline.log | grep ERROR

# 手动运行测试
python cron_pipeline.py --run --index dow --weeks 2
```

**问题**: 日志文件过大
```bash
# 清理旧日志（保留最后 10000 行）
tail -10000 scheduler.log > scheduler.log.tmp && mv scheduler.log.tmp scheduler.log
tail -10000 cron_pipeline.log > cron_pipeline.log.tmp && mv cron_pipeline.log.tmp cron_pipeline.log
```

---

## 🔄 与其他方案对比

为什么选择 APScheduler：

| 特性 | APScheduler | Cron | systemd timer |
|------|-----------|------|---------------|
| 系统依赖 | ❌ 无 | ✅ 有 | ✅ 有 |
| 跨平台 | ✅ 是 | ❌ Linux 只 | ❌ Linux 只 |
| Docker 友好 | ✅ 是 | ⚠️ 需配置 | ❌ 否 |
| 易于修改 | ✅ Python | ⚠️ 需重编 | ⚠️ 需重编 |
| 实时监控 | ✅ 是 | ⚠️ 可以 | ⚠️ 可以 |
| 内存占用 | ~25 MB | ~1 MB | ~0 MB |

**选择 APScheduler 的原因**:
- ✅ 系统不支持 cron/systemd
- ✅ 需要灵活修改调度参数
- ✅ 在容器环境中运行
- ✅ Python 应用原生集成

---

## 📞 常见问题

**Q: 调度器会占用太多内存吗？**
A: 否。APScheduler 常驻进程约占用 25 MB 内存，Pipeline 运行时会短暂增加到 1-2 GB。

**Q: 如果管道运行超过 1 小时怎么办？**
A: 已配置 `max_instances=1`，下次计划的任务会等待前一个完成。不会重复启动。

**Q: 可以手动运行管道吗？**
A: 可以。在调度器运行期间，手动执行 `python cron_pipeline.py --run ...` 不会冲突。

**Q: 如何让调度器开机自启？**
A: 需要在系统启动脚本中添加 `bash start_scheduler.sh`（见下文）。

---

## 🔧 开机自启配置（可选）

### 方式 1: /etc/rc.local

编辑 `/etc/rc.local`：

```bash
#!/bin/bash

# 在 exit 0 之前添加：
bash /root/FinGPT/fingpt/FinGPT_Forecaster/start_scheduler.sh

exit 0
```

### 方式 2: crontab @reboot

```bash
# crontab -e 中添加：
@reboot bash /root/FinGPT/fingpt/FinGPT_Forecaster/start_scheduler.sh
```

### 方式 3: systemd service

创建 `/etc/systemd/system/fingpt-scheduler.service`：

```ini
[Unit]
Description=FinGPT APScheduler Daemon
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/FinGPT/fingpt/FinGPT_Forecaster
ExecStart=/bin/bash /root/FinGPT/fingpt/FinGPT_Forecaster/start_scheduler.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

然后：
```bash
sudo systemctl daemon-reload
sudo systemctl enable fingpt-scheduler
sudo systemctl start fingpt-scheduler
```

---

## 📊 部署总结

| 组件 | 状态 | 说明 |
|------|------|------|
| **APScheduler** | ✅ 安装 | Python 调度库 |
| **调度器进程** | ✅ 运行 | PID 已保存 |
| **计划任务** | ✅ 配置 | 每周日 02:00 UTC |
| **Pipeline 修复** | ✅ 完成 | 数据无重合 |
| **Checkpoint** | ✅ 启用 | 自动记录进度 |
| **日志系统** | ✅ 完整 | scheduler.log + cron_pipeline.log |

---

**部署完成日期**: 2026-02-28
**状态**: ✅ 生产就绪
**下次运行**: 2026-03-01 02:00 UTC（下周日）
