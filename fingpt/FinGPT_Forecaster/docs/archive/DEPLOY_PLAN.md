# FinGPT-Forecaster 部署与运行计划

本计划旨在指导用户在当前 Linux 服务器（配备 RTX 4090）上运行 FinGPT-Forecaster 项目。

## 一、 准备工作 (基础设施)

### 1. 确认网络加速
- [x] **状态确认**: 已通过平台开通网络加速。
- [x] **技术原理**: 通过内网透明网关 (`10.60.42.12`) 直连专线访问 Google/Finnhub。

### 2. 配置环境变量
- [x] **状态确认**: 已在 `/root/FinGPT/fingpt/FinGPT_Forecaster/.env` 中配置 `HF_TOKEN` 和 `FINNHUB_KEY`。
- [!] **注意**: `app.py` 中预期的变量名是 `FINNHUB_API_KEY`，运行时需注意映射。

---

## 二、 环境配置 (Terminal 执行)

### 1. 完善虚拟环境
请执行以下命令来安装必要的库：
```bash
# 激活环境
conda activate fingpt

# 安装缺失依赖
pip install gradio yfinance nvidia-ml-py3 python-dotenv
```

---

## 三、 运行与测试

### 1. 启动 Web 界面
在 `/root/FinGPT/fingpt/FinGPT_Forecaster` 目录下运行：
```bash
conda activate fingpt

# 映射并导入环境变量后启动
export FINNHUB_API_KEY=$(grep FINNHUB_KEY .env | cut -d '=' -f2)
export HF_TOKEN=$(grep HF_TOKEN .env | cut -d '=' -f2)

python app.py
```

### 2. 使用步骤
1. **访问 URL**: 程序启动后会输出一个 `http://127.0.0.1:7860` 的地址。
2. **输入 Ticker**: 输入 `AAPL` 或 `TSLA`。
3. **提交**: 点击 Submit 后开始生成分析。

---

## 四、 后续进阶 (可选)

1. **训练自己的模型**: 
   - 准备数据：通过 `prepare_data.ipynb` 生成训练集。
   - 执行训练：运行 `bash train.sh`（已配置好 DeepSpeed）。
2. **多显卡优化**: 
   - 若显存不足，可在 `app.py` 中调整 `load_in_8bit=True` 或使用 `4bit` 量化。
