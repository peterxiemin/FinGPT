# Cron Pipeline 数据重合问题修复

## 问题描述

在原始的 `cron_pipeline.py` 设计中，`get_time_window()` 函数在每次运行时都使用固定的逻辑：

```python
def get_time_window(weeks_back=2):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7 * weeks_back)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
```

这导致：

```
周日1 运行: 获取 [周日1-14, 周日1] 的数据
周日2 运行: 获取 [周日2-14, 周日2] 的数据

重合数据: [周日2-14, 周日1] ← 一周的数据被重复使用！
```

### 影响

- ❌ 训练数据中存在重复样本
- ❌ 模型验证集数据泄漏风险
- ❌ 无法准确追踪哪些数据被使用过

---

## 解决方案

实现了 **checkpoint 机制**，记录每次运行的截止时间：

### 修改的函数

文件: `cron_pipeline.py` 第 25-45 行

**新实现**:

```python
def get_time_window(weeks_back=2):
    """Calculate start_date and end_date for the pipeline (non-overlapping runs).

    On first run: returns [now - weeks_back, now]
    On subsequent runs: returns [last_run_end_date, now] to avoid data overlap
    """
    checkpoint_file = "pipeline_checkpoint.json"
    end_date = datetime.now()

    # Check if we have a previous checkpoint
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                # Start from where the last run ended to avoid overlap
                start_date = datetime.fromisoformat(checkpoint["last_end_date"])
                logger.info(f"Using checkpoint: last run ended at {checkpoint['last_end_date']}")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Checkpoint file corrupted ({e}); falling back to weeks_back={weeks_back}")
            start_date = end_date - timedelta(days=7 * weeks_back)
    else:
        # First run: look back weeks_back weeks
        logger.info(f"No checkpoint found; looking back {weeks_back} weeks")
        start_date = end_date - timedelta(days=7 * weeks_back)

    # Save checkpoint for next run
    try:
        with open(checkpoint_file, 'w') as f:
            json.dump({
                "last_end_date": end_date.isoformat(),
                "last_run_time": datetime.now().isoformat(),
                "index_name": "dow"
            }, f, indent=2)
        logger.info(f"Updated checkpoint: next run will start from {end_date.isoformat()}")
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")

    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
```

### 工作流程

```
首次运行:
  • pipeline_checkpoint.json 不存在
  • 回溯 weeks_back=2 周
  • 获取 [2周前, 现在] 的数据
  • 保存 checkpoint

后续运行（例如一周后）:
  • 读取 pipeline_checkpoint.json
  • 从上次的 end_date 开始
  • 获取 [上次end_date, 现在] 的数据
  • 更新 checkpoint

结果: 零数据重合！
```

### 容错机制

- ✅ Checkpoint 损坏 → 自动回退到 `weeks_back` 逻辑
- ✅ Checkpoint 缺少字段 → 自动回退到 `weeks_back` 逻辑
- ✅ 文件保存失败 → 记录错误，继续运行

---

## 测试验证

### 测试文件

创建了 `tests/test_cron_pipeline.py`，包含 6 个完整的单元测试：

#### 1. 基础功能测试

- ✅ `test_first_run_uses_weeks_back` - 首次运行回溯2周
- ✅ `test_second_run_continues_from_first_end` - 第二次运行从上次结束继续
- ✅ `test_no_data_overlap` - 验证无数据重合
- ✅ `test_checkpoint_persistence` - 验证 checkpoint 持久化

#### 2. 错误处理测试

- ✅ `test_corrupted_checkpoint_recovery` - 损坏的 checkpoint 自动恢复
- ✅ `test_missing_last_end_date_in_checkpoint` - 缺少字段自动恢复

### 测试结果

```
pytest tests/test_cron_pipeline.py -v

============================= test session starts ==============================
tests/test_cron_pipeline.py::TestTimeWindowNonOverlap::test_first_run_uses_weeks_back PASSED [ 16%]
tests/test_cron_pipeline.py::TestTimeWindowNonOverlap::test_second_run_continues_from_first_end PASSED [ 33%]
tests/test_cron_pipeline.py::TestTimeWindowNonOverlap::test_no_data_overlap PASSED [ 50%]
tests/test_cron_pipeline.py::TestTimeWindowNonOverlap::test_checkpoint_persistence PASSED [ 66%]
tests/test_cron_pipeline.py::TestTimeWindowEdgeCases::test_corrupted_checkpoint_recovery PASSED [ 83%]
tests/test_cron_pipeline.py::TestTimeWindowEdgeCases::test_missing_last_end_date_in_checkpoint PASSED [100%]

============================== 6 passed in 1.34s ===============================
```

✅ **所有测试通过！**

---

## 使用说明

### 首次使用

```bash
python cron_pipeline.py --run --index dow --weeks 2
```

- 获取过去 2 周的数据
- 创建 `pipeline_checkpoint.json`

### 后续运行（自动执行，每周一次）

```bash
# 下周运行（Crontab 自动触发）
python cron_pipeline.py --run --index dow --weeks 2
```

- 读取 checkpoint
- 获取从上次结束到现在的数据（增量）
- 更新 checkpoint

### Checkpoint 文件示例

```json
{
  "last_end_date": "2026-02-28T18:03:22.436705",
  "last_run_time": "2026-02-28T18:03:22.436836",
  "index_name": "dow"
}
```

### 重置 Checkpoint

如需完全重新开始，删除 checkpoint 文件：

```bash
rm pipeline_checkpoint.json
```

下次运行会重新初始化。

---

## 修改总结

| 项目 | 详情 |
|------|------|
| **修改文件** | `cron_pipeline.py` |
| **修改函数** | `get_time_window()` (第 25-45 行) |
| **新增文件** | `tests/test_cron_pipeline.py` |
| **新增文件** | `pipeline_checkpoint.json` (运行时生成) |
| **测试覆盖** | 6 个单元测试，100% 通过 |
| **向后兼容** | ✅ 完全兼容（首次运行自动回溯） |

---

## 后续建议

1. **监控 checkpoint** - 定期检查 `pipeline_checkpoint.json` 是否更新正确
2. **日志追踪** - 查看 `cron_pipeline.log` 中的 "Using checkpoint" 消息
3. **定期备份** - 考虑备份 checkpoint 以防意外删除
4. **扩展支持** - 如需支持多个指数（dow/euro/crypto），可扩展 checkpoint 为字典结构

---

**修复日期**: 2026-02-28
**修复版本**: cron_pipeline.py v2
**状态**: ✅ 生产就绪
