import pytest
import pandas as pd
import os
import json
from unittest.mock import patch
from data import get_returns, get_news, get_basics, prepare_data_for_symbol

# 统一测试时间：选择最近一个稳定的时间窗口（约6周），确保有足够数据生成 Prompt
TEST_START = "2026-01-01"
TEST_END = "2026-02-15"

def test_get_returns_format():
    """测试股价获取函数是否能正确处理 yfinance 的 MultiIndex 格式"""
    symbol = "AAPL"
    # 使用统一的时间窗口
    df = get_returns(symbol, TEST_START, TEST_END)
    
    required_columns = ['Start Date', 'Start Price', 'End Date', 'End Price', 'Weekly Returns', 'Bin Label']
    for col in required_columns:
        assert col in df.columns, f"缺失关键列: {col}"
    
    assert len(df) > 0, "不应返回空数据"
    # yfinance 最近返回的是 Series 或 float，取决于 pandas 版本
    val = df['Weekly Returns'].iloc[0]
    assert isinstance(val, (float, int)) or hasattr(val, '__float__')
    assert isinstance(df['Bin Label'].iloc[0], str)

def test_get_news_content():
    """测试新闻获取功能（真实 API 调用）"""
    symbol = "AAPL"
    # 使用统一的时间窗口
    df = get_returns(symbol, TEST_START, TEST_END)
    
    # 获取新闻
    df_with_news = get_news(symbol, df)
    
    assert 'News' in df_with_news.columns
    # 验证新闻内容是否为合法的 JSON 字符串
    news_json = df_with_news['News'].iloc[0]
    news_data = json.loads(news_json)
    assert isinstance(news_data, list)
    
    # 只要 API 调通，我们验证结构
    if len(news_data) > 0:
        assert 'headline' in news_data[0]
        assert 'date' in news_data[0]

def test_get_basics_content():
    """测试基本面获取功能（真实 API 调用）"""
    symbol = "AAPL"
    df = get_returns(symbol, TEST_START, TEST_END)
    
    # 测试获取基本面财务数据
    df_with_basics = get_basics(symbol, df, TEST_START, always=True)
    
    assert 'Basics' in df_with_basics.columns
    basics_json = df_with_basics['Basics'].iloc[0]
    basics_data = json.loads(basics_json)
    
    # 验证结构
    assert isinstance(basics_data, dict)
    if basics_data:
        assert 'period' in basics_data

def test_prepare_data_full_lifecycle():
    """测试完整的数据准备生命周期"""
    symbol = "AAPL"
    # 使用项目 test 下的专门数据目录
    data_dir = os.path.join(os.path.dirname(__file__), "output_data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    # 使用统一的时间窗口
    start = TEST_START
    end = TEST_END
    
    df = prepare_data_for_symbol(symbol, data_dir, start, end, with_basics=True)
    
    # 验证返回的 DataFrame
    assert not df.empty
    assert 'News' in df.columns
    assert 'Basics' in df.columns
    
    # 验证 CSV 文件是否实际写入
    expected_csv = os.path.join(data_dir, f"{symbol}_{start}_{end}.csv")
    assert os.path.exists(expected_csv)
    
    # --- 添加文件分析 ---
    analyze_output_csv(expected_csv)
    
    return symbol, data_dir, start, end

def analyze_output_csv(file_path):
    """对生成的原始数据 CSV 进行统计分析"""
    print(f"\n" + "="*50)
    print(f"📊 原始数据统计: {os.path.basename(file_path)}")
    df = pd.read_csv(file_path)
    print(f"• 总样本量 (周): {len(df)}")
    print(f"• 时间范围: {df['Start Date'].min()} -> {df['End Date'].max()}")
    print(f"• 涨跌分布: {df['Bin Label'].value_counts().to_dict()}")
    
    # 检查新闻密度
    news_lens = df['News'].apply(lambda x: len(json.loads(x)))
    print(f"• 平均每周抓取新闻: {news_lens.mean():.1f} 条")
    
    # 检查基本面覆盖
    has_basics = df['Basics'].apply(lambda x: x != '{}' and x != '"{}"').sum()
    print(f"• 财务数据覆盖率: {has_basics}/{len(df)} 周")
    print("="*50)

def test_query_gpt4_lifecycle():
    """测试 LLM 预测分析全流程 (依赖 DeepSeek/OpenRouter)"""
    from data import query_gpt4
    
    # 1. 首先准备基础数据
    symbol, data_dir, start, end = test_prepare_data_full_lifecycle()
    
    # 2. 调用 LLM 进行分析预测
    # 为了测试速度，我们只对一两周的数据进行询问
    model_name = os.environ.get("OPENAI_MODEL", "deepseek/deepseek-chat")
    model_suffix = model_name.split('/')[-1]
    
    print(f"\n开始测试 LLM 预测 (DeepSeek)... 目标文件: {symbol}_{start}_{end}_{model_suffix}.csv")
    query_gpt4([symbol], data_dir, start, end, min_past_weeks=1, max_past_weeks=1, with_basics=True)
    
    # 3. 验证预测结果文件
    prediction_csv = os.path.join(data_dir, f"{symbol}_{start}_{end}_{model_suffix}.csv")
    assert os.path.exists(prediction_csv), "预测结果 CSV 未生成"
    
    pred_df = pd.read_csv(prediction_csv)
    assert len(pred_df) > 0, "预测结果为空"
    assert "prompt" in pred_df.columns
    assert "answer" in pred_df.columns
    
    # 验证答案内容是否包含预期的关键词 (比如分析或预测)
    last_answer = pred_df['answer'].iloc[-1]
    assert len(str(last_answer)) > 100, "LLM 回答过短，可能调用失败"
    
    # --- 添加 LLM 分析文件的深度统计 ---
    analyze_gpt4_csv(prediction_csv)

def analyze_gpt4_csv(file_path):
    """对 LLM 生成的分析报告进行质量核对"""
    print(f"\n" + "🤖 LLM 生成质量报告 ".center(50, "="))
    df = pd.read_csv(file_path)
    print(f"• 生成分析总数: {len(df)}")
    
    # 结构化验证
    last_ans = str(df['answer'].iloc[-1])
    required = ["[Positive Developments]", "[Potential Concerns]", "[Prediction & Analysis]"]
    found = [r for r in required if r in last_ans]
    
    print(f"• 结构完整性: {len(found)}/{len(required)}")
    if len(found) == len(required):
        print("  ✅ 段落结构符合证券分析师规范")
    else:
        print(f"  ❌ 缺失段落: {[r for r in required if r not in found]}")
        
    # 长度验证
    avg_len = df['answer'].apply(lambda x: len(str(x))).mean()
    print(f"• 平均分析字数: {int(avg_len)} 字")
    print("="*50 + "\n")

def test_bin_mapping_logic():
    """测试涨跌幅分桶逻辑"""
    from data import bin_mapping

    assert bin_mapping(0.005) == "U1"
    assert bin_mapping(-0.023) == "D3"
    assert bin_mapping(0.06) == "U5+"
    assert bin_mapping(-0.15) == "D5+"


# ---------------------------------------------------------------------------
# create_dataset 边界测试（mock gpt4_to_llama，不调用真实 API）
# ---------------------------------------------------------------------------

_MOCK_DATA_3 = {
    "prompt":  ["prompt_A", "prompt_B", "prompt_C"],
    "answer":  ["answer_A", "answer_B", "answer_C"],
    "period":  ["2026-01-08_2026-01-15", "2026-01-15_2026-01-22", "2026-01-22_2026-01-29"],
    "label":   ["U1", "D2", "U3"],
}


def test_create_dataset_empty_test_split_ok():
    """train_ratio=1.0 时所有样本进 train，test 应为空 schema，不应 crash。"""
    from data import create_dataset

    with patch("data.gpt4_to_llama", return_value=_MOCK_DATA_3):
        result = create_dataset(
            ["AAPL"], "/fake/dir", "2026-01-01", "2026-02-15",
            train_ratio=1.0, with_basics=True
        )

    assert len(result["train"]) == 3, "train 应含全部 3 条样本"
    assert len(result["test"]) == 0,  "test 应为空（不是 crash）"
    assert set(result["test"].column_names) == set(result["train"].column_names), \
        "test 与 train 应有相同的 schema"


def test_create_dataset_normal_split():
    """train_ratio=0.8，3 条样本 → train=2, test=1。"""
    from data import create_dataset

    with patch("data.gpt4_to_llama", return_value=_MOCK_DATA_3):
        result = create_dataset(
            ["AAPL"], "/fake/dir", "2026-01-01", "2026-02-15",
            train_ratio=0.8, with_basics=True
        )

    # round(0.8 * 3) = 2
    assert len(result["train"]) == 2
    assert len(result["test"]) == 1


def test_create_dataset_no_samples_raises():
    """所有 symbol 均返回 0 条 prompt 时，应抛出 ValueError（而非 Trainer 内部 crash）。"""
    from data import create_dataset

    empty = {"prompt": [], "answer": [], "period": [], "label": []}
    with patch("data.gpt4_to_llama", return_value=empty):
        with pytest.raises(ValueError, match="No training samples"):
            create_dataset(
                ["AAPL", "MSFT"], "/fake/dir", "2026-01-01", "2026-01-08"
            )
