# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## IMPORTANT: Git Rules

**Never push or submit any changes to the upstream repository (`AI4Finance-Foundation/FinGPT`).** All changes must only go to the fork (`peterxiemin/FinGPT`). Never create PRs targeting the upstream repo.

## Project Overview

FinGPT is an open-source financial LLM framework by AI4Finance Foundation. It provides full-stack tools for financial NLP including sentiment analysis, stock price forecasting, RAG, and multi-agent systems. The most actively developed module is **FinGPT_Forecaster**.

## Commands

### Running Tests (FinGPT_Forecaster)

Tests must be run from the Forecaster directory since `data.py` uses relative imports:

```bash
cd fingpt/FinGPT_Forecaster
python -m pytest tests/test_data.py -v
```

Run a single test:
```bash
cd fingpt/FinGPT_Forecaster
python -m pytest tests/test_data.py::test_bin_mapping_logic -v
```

Tests that hit real APIs (Finnhub, yfinance, OpenRouter) require a valid `.env` file.

### Running the Forecaster Web App

```bash
cd fingpt/FinGPT_Forecaster
./manage.sh start   # Start in background (logs to app.log)
./manage.sh stop    # Stop
./manage.sh status  # Check status
./manage.sh logs    # Tail logs
```

Or directly: `python app.py` (requires GPU with sufficient VRAM for Llama 3.1-8B)

### Data Pipeline (Training Data Generation)

```bash
cd fingpt/FinGPT_Forecaster
python data_pipeline.py --index dow --start_date 2023-01-01 --end_date 2023-09-01
```

This runs 3 steps: acquire raw stock/news data → LLM analysis via OpenRouter → save HuggingFace dataset.

### LoRA Fine-tuning

```bash
cd fingpt/FinGPT_Forecaster
python train_lora.py --dataset ./data/<dataset_path> --base_model llama3 --run_name my-run
```

Key args: `--num_epochs`, `--batch_size`, `--learning_rate`, `--load_in_4bit`

### Automated Continuous Pipeline

```bash
cd fingpt/FinGPT_Forecaster
python cron_pipeline.py --run   # Runs data pipeline → fine-tuning → deployment
```

**Important**: This pipeline includes a Checkpoint mechanism to prevent data overlap (see `CRON_PIPELINE_FIX.md`).

### Scheduling the Pipeline (APScheduler)

The project uses **APScheduler** for automatic execution (every Sunday at 02:00 UTC):

```bash
# Check scheduler status
bash check_scheduler.sh

# Start scheduler
bash start_scheduler.sh

# Stop scheduler
bash stop_scheduler.sh

# View logs
tail -f scheduler.log
```

See `APSCHEDULER_SETUP.md` for detailed configuration.

**Note**: For other scheduling methods (cron, systemd timer), see `SCHEDULER_TEMPLATE.md`.

## Architecture (FinGPT_Forecaster)

This module is a pipeline for LLM-based stock forecasting. The data flow is:

```
yfinance + Finnhub → data.py → prompt.py → LLM (OpenRouter/DeepSeek) → training dataset
                                                                          ↓
                                                                    train_lora.py → LoRA weights
                                                                                    ↓
                                                                              app.py (Gradio)
```

**Key files:**
- `data.py` — Core data acquisition: `get_returns()` (yfinance weekly prices), `get_news()` (Finnhub), `get_basics()` (quarterly financials), `prepare_data_for_symbol()`, `query_gpt4()` (LLM analysis via OpenRouter), `create_dataset()` (HF format)
- `prompt.py` — Generates structured prompts from the acquired data
- `app.py` — Gradio UI; loads base model from `/model/llm/Meta-Llama-3.1-8B-Instruct` and LoRA weights from `model_config.json` or HuggingFace
- `train_lora.py` — LoRA fine-tuning with HuggingFace Trainer + peft; saves to `./finetuned_models/`
- `data_pipeline.py` — Orchestrates the full data→LLM→dataset pipeline for an index
- `cron_pipeline.py` — Automated weekly pipeline: data → fine-tune → deploy (updates `model_config.json`, restarts app.py). Features Checkpoint mechanism to avoid data overlap between runs.
- `apscheduler_daemon.py` — APScheduler daemon that triggers `cron_pipeline.py` on schedule (every Sunday 02:00 UTC)
- `rate_limiter.py` — Disk-cache-based global rate limiter (multi-process safe); Finnhub: 30/min, yfinance: 1/sec, OpenRouter: 50/min
- `indices.py` — Symbol lists: `DOW_30`, `EURO_STOXX_50`, `CRYPTO`
- `model_config.json` — Runtime override: `latest_model_path` specifies which LoRA weights `app.py` loads
- `utils.py` — LoRA module helpers, dataset loading, answer parsing

**LLM output format** (enforced by system prompt and validated in tests):
```
[Positive Developments]: ...
[Potential Concerns]: ...
[Prediction & Analysis]: ...
```

**Return bucketing** (`bin_mapping` in `data.py`): Weekly returns are bucketed into labels like `U1` (up ~1%), `D3` (down ~3%), `U5+` (up >5%), `D5+` (down >5%).

## Environment Configuration

Copy `.env` in the Forecaster directory:
```
FINNHUB_KEY=<finnhub api key>
OPENAI_KEY=<openrouter api key>
OPENAI_MODEL=deepseek/deepseek-chat   # or any OpenRouter model
HF_TOKEN=<huggingface token>
HTTP_PROXY=<optional proxy>
```

The `OPENAI_MODEL` env var controls which LLM is used for analysis; defaults to `deepseek/deepseek-chat`. The model suffix is appended to output CSV filenames.

## Module Map

| Module | Purpose |
|--------|---------|
| `FinGPT_Forecaster` | Stock price prediction with LLM; Gradio app; LoRA training pipeline |
| `FinGPT_Sentiment_Analysis_v3` | Best sentiment analysis (F1=0.882 FPB); single RTX3090 training |
| `FinGPT_Benchmark` | Multi-task instruction tuning (sentiment, NER, headline, relation extraction) |
| `FinGPT_RAG` | RAG-augmented sentiment; multisource news scraping |
| `FinGPT_FinancialReportAnalysis` | Earnings call & financial report analysis with RAG |
| `FinGPT_MultiAgentsRAG` | Multi-agent RAG with MMLU/HaluEval/TruthfulQA evaluation |
| `FinGPT_Others` | Trading bots, robo-advisors, low-code examples (mostly Jupyter notebooks) |

## Test Reference Data

Test dates are unified at `2026-01-01` to `2026-02-15`. Reference CSV for AAPL is at `fingpt/FinGPT_Forecaster/tests/output_data/AAPL_2026-01-01_2026-02-15.csv`.
