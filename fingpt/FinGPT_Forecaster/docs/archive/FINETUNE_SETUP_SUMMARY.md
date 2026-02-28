# FinGPT Forecaster 微调环境与代码调整总结

本文档汇总了本次 Session 中为了实现 Llama 3 (QLoRA) 微调所做的所有代码调整、环境修复及操作步骤。

## 1. 代码修改汇总

### `train_lora.py` (核心微调脚本)
- **4-bit 量化支持**: 增加了 `--load_in_4bit` 参数，通过 `bitsandbytes` 实现 QLoRA，大幅降低显存占用（从原文的 13GB+ 降至兼容 24G 显卡剩余空间）。
- **兼容性修复**:
    - 将 `evaluation_strategy` 更新为 `eval_strategy`（适配 Transformers v4.4x+）。
    - 修复了 `peft` 导入名错误（`prepare_model_for_int8_training` -> `prepare_model_for_kbit_training`）。
    - 在 `model.generate` 中增加 `max_new_tokens=512`，避免因 Prompt 过长导致的 `ValueError`。
- **鲁棒性增强**:
    - 增加了 `load_dotenv()`，自动读取 `.env` 中的代理和 Token。
    - 增加了对评估数据集大小的检查，防止小样本量时的 `IndexError`。
    - 允许通过 `WANDB_MODE=disabled` 跳过 WandB 登录。

### `utils.py` (工具类)
- **Llama 3 支持**: 在 `lora_module_dict` 中增加了 Llama 3 的层名称映射。
- **本地路径映射**: 在 `parse_model_name` 中增加了 `llama3` 选项，直接指向本地路径 `/model/llm/Meta-Llama-3.1-8B-Instruct`。

### `export_dataset.py` (新增脚本)
- **多格式导出**: 支持将 LLM 生成的新闻分析 CSV 转换为：
    1. **JSONL 格式**: 用于数据质量人工预览。
    2. **HF Disk 格式**: 完美契合原项目的 `datasets.load_from_disk` 逻辑。

### `.env` (环境变量)
- **格式修复**: 修复了由于文本合并导致的 `HF_TOKEN` 与 `HTTP_PROXY` 粘连问题。

---

## 2. 环境依赖更新
执行了以下库的安装与对齐：
- `bitsandbytes`: 实现 4-bit 量化。
- `scikit-learn` & `rouge_score`: 用于训练过程中的指标计算。
- `tensorboard`: 避免 `SummaryWriter` 报错。
- `deepspeed`: 虽然本次单卡训练未使用，但补齐了 `transformers` 的强制依赖检查。
- `peft==0.12.0`: 对齐版本以支持最新的架构。

---

## 3. 运行指南

### 数据转换
```bash
PYTHONPATH=. python export_dataset.py
```

### 启动评估/训练 (QLoRA 模式)
```bash
WANDB_MODE=disabled PYTHONPATH=. python train_lora.py \
--run_name aapl-llama3-finetune-qlora \
--base_model llama3 \
--dataset aapl-test \
--max_length 1024 \
--batch_size 1 \
--gradient_accumulation_steps 4 \
--learning_rate 1e-4 \
--num_epochs 10 \
--ds_config none \
--load_in_4bit
```

---
**状态**: 训练已于后台启动，详细进度请查看 `app.log` 或实时输出。
