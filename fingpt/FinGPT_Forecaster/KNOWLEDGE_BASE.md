# FinGPT Forecaster 知识库和快速查询

这个文档汇总了在FinGPT项目中解决的所有问题和沉淀的最佳实践。

## 问题索引

### 1. 数据重合问题
**问题**: 定时运行数据管道时，相邻运行有数据重合
**症状**: 训练数据中存在重复样本，模型性能下降
**查询**: `CRON_PIPELINE_FIX.md`
**关键字**: Checkpoint, incremental data, pipeline overlap

**快速修复**:
```python
# 在 get_time_window() 中实现 Checkpoint 机制
if os.path.exists("pipeline_checkpoint.json"):
    with open("pipeline_checkpoint.json") as f:
        checkpoint = json.load(f)
        start_date = datetime.fromisoformat(checkpoint["last_end_date"])
else:
    start_date = end_date - timedelta(days=7 * weeks_back)
```

---

### 2. 定时任务调度
**问题**: 需要周期性自动运行数据管道
**环境约束**: 系统无cron/systemd支持
**查询**: `SCHEDULER_TEMPLATE.md` 或 `APSCHEDULER_SETUP.md`
**关键字**: scheduling, cron, APScheduler, daemon

**快速决策**:
```
有cron? → 用cron
有systemd? → 用systemd timer
都没有? → 用APScheduler
```

**快速部署**:
```bash
pip install APScheduler
# 复制 apscheduler_daemon.py, start_scheduler.sh 等
bash start_scheduler.sh
```

---

## 文档导航

### 按场景查找

#### "我想了解数据管道如何避免重合"
→ `CRON_PIPELINE_FIX.md` → Checkpoint 机制部分

#### "我需要配置定时运行"
→ `SCHEDULER_TEMPLATE.md` → 快速决策树
→ `APSCHEDULER_SETUP.md` → 详细配置

#### "我想复用这个定时任务的解决方案"
→ `SCHEDULER_TEMPLATE.md` → 参考实现部分
→ 复制 `apscheduler_daemon.py`, `start_scheduler.sh` 等

#### "我需要理解系统的完整架构"
→ `DEPLOYMENT_SUMMARY.md` → 完整的系统架构
→ `/root/FinGPT/CLAUDE.md` → 项目概览

#### "调度器出问题了，我需要调试"
→ `APSCHEDULER_SETUP.md` → 故障排查部分
→ `bash check_scheduler.sh`

---

### 按组件查找

#### cron_pipeline.py
**功能**: 自动化数据处理管道
**关键修改**: Checkpoint 机制（v2）
**测试**: `tests/test_cron_pipeline.py`
**文档**: `CRON_PIPELINE_FIX.md`

#### apscheduler_daemon.py
**功能**: 定时任务调度器
**依赖**: APScheduler
**启动**: `bash start_scheduler.sh`
**文档**: `APSCHEDULER_SETUP.md`

#### pipeline_checkpoint.json
**功能**: 记录管道执行进度
**格式**: JSON
**生成**: 运行 `cron_pipeline.py` 时自动创建
**重置**: `rm pipeline_checkpoint.json`

---

## 最佳实践

### 1. 增量数据处理
- ✅ 实现 Checkpoint 机制记录上次进度
- ✅ 后续运行从上次结束处继续
- ✅ 提供 checkpoint 损坏时的回退方案

### 2. 定时任务设计
- ✅ 实现容错机制（自动重试）
- ✅ 记录详细日志（便于追踪）
- ✅ 提供管理脚本（启动/停止/检查）

### 3. 代码可复用性
- ✅ 将特定实现提取为通用模板
- ✅ 记录快速决策树和参数映射
- ✅ 提供复制-粘贴可用的脚本

### 4. 文档沉淀
- ✅ 为每个解决方案创建独立文档
- ✅ 包含快速参考和详细说明
- ✅ 建立知识库和快速查询系统

---

## 快速命令速查

### 调度器管理
```bash
# 检查状态
bash check_scheduler.sh

# 启动
bash start_scheduler.sh

# 停止
bash stop_scheduler.sh

# 查看日志
tail -f scheduler.log
```

### 管道管理
```bash
# 手动运行
python cron_pipeline.py --run --index dow --weeks 2

# 重置进度
rm pipeline_checkpoint.json

# 查看进度
cat pipeline_checkpoint.json
```

### 测试
```bash
# 运行所有测试
python -m pytest tests/test_cron_pipeline.py -v

# 运行特定测试
python -m pytest tests/test_cron_pipeline.py::TestTimeWindowNonOverlap::test_first_run_uses_weeks_back -v
```

---

## 知识点速记

### Checkpoint 机制
```
首次运行: [now - weeks_back, now]
后续运行: [last_checkpoint, now]
结果: 零数据重合
```

### APScheduler CronTrigger
```python
# 每周日 02:00
CronTrigger(day_of_week=6, hour=2, minute=0)

# day_of_week: 0=Mon, 1=Tue, ..., 6=Sun
# hour: 0-23 (UTC)
# minute: 0-59
```

### 定时任务三要素
1. **调度器** (APScheduler) → 何时执行
2. **脚本** (cron_pipeline.py) → 执行什么
3. **日志** (scheduler.log) → 如何监控

---

## 相关文件清单

### 文档
- `SCHEDULER_TEMPLATE.md` - 通用定时任务模板
- `CRON_PIPELINE_FIX.md` - 数据重合问题修复
- `APSCHEDULER_SETUP.md` - APScheduler 配置指南
- `DEPLOYMENT_SUMMARY.md` - 完整部署记录
- `KNOWLEDGE_BASE.md` - 本文档（知识库）

### 代码
- `cron_pipeline.py` - 数据管道（含 Checkpoint）
- `apscheduler_daemon.py` - 调度器主程序
- `start_scheduler.sh` - 启动脚本
- `stop_scheduler.sh` - 停止脚本
- `check_scheduler.sh` - 状态检查脚本

### 测试
- `tests/test_cron_pipeline.py` - 6 个单元测试

### 配置
- `pipeline_checkpoint.json` - 运行进度记录（自动生成）
- `.scheduler.pid` - 调度器 PID 记录（自动生成）
- `model_config.json` - 模型配置

---

## 学习路径建议

### 快速上手 (15分钟)
1. 阅读本文档的"问题索引"部分
2. 查看相关的"快速修复"或"快速决策"
3. 运行 `bash check_scheduler.sh` 验证状态

### 深入理解 (1小时)
1. 阅读 `CRON_PIPELINE_FIX.md` 的"解决方案"部分
2. 阅读 `SCHEDULER_TEMPLATE.md` 的快速决策树
3. 查看 `apscheduler_daemon.py` 的源代码

### 完全掌握 (3小时)
1. 通读所有文档
2. 运行所有单元测试
3. 尝试修改参数并重新启动调度器

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-02-28 | 初始部署，包含 Checkpoint 机制和 APScheduler |

---

## 相关资源

### 内部文档
- `/root/FinGPT/CLAUDE.md` - FinGPT 项目指南
- `/root/.claude/projects/-root-FinGPT/memory/MEMORY.md` - Claude 记忆库

### 外部文档
- [APScheduler 官方文档](https://apscheduler.readthedocs.io/)
- [FinGPT GitHub](https://github.com/AI4Finance-Foundation/FinGPT)

---

**最后更新**: 2026-02-28
**维护者**: Claude Code
**状态**: 生产就绪 ✅
