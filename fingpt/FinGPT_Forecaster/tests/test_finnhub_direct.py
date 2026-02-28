import pytest
import pandas as pd
import os
import json
from data import get_news, get_basics
from datetime import datetime

# Mock a DataFrame that usually comes from yfinance
def get_mock_df():
    # AAPL dummy date range
    dates = pd.date_range(start="2026-02-15", end="2026-02-22", freq='W')
    df = pd.DataFrame({
        'Start Date': dates[:-1],
        'End Date': dates[1:],
        'Start Price': [230.0],
        'End Price': [235.0],
        'Weekly Returns': [0.0217],
        'Bin Label': ['U2']
    })
    return df

def test_finnhub_news_direct():
    """Directly test Finnhub news fetching without yfinance dependency"""
    symbol = "AAPL"
    df = get_mock_df()
    
    # This calls our get_news logic which uses finnhub_client
    df_with_news = get_news(symbol, df)
    
    assert 'News' in df_with_news.columns
    news_json = df_with_news['News'].iloc[0]
    news_data = json.loads(news_json)
    
    assert isinstance(news_data, list), "News should be a list"
    print(f"\n[Test Finnhub] Successfully fetched {len(news_data)} news items for {symbol}")
    if len(news_data) > 0:
        print(f"Sample news: {news_data[0]['headline']}")

def test_finnhub_basics_direct():
    """Directly test Finnhub basics (financials) fetching"""
    symbol = "AAPL"
    df = get_mock_df()
    
    # This calls our get_basics logic
    # always=True ensures we get data even if it's not a 'earnings week'
    df_with_basics = get_basics(symbol, df, "2026-01-01", always=True)
    
    assert 'Basics' in df_with_basics.columns
    basics_json = df_with_basics['Basics'].iloc[0]
    basics_data = json.loads(basics_json)
    
    assert isinstance(basics_data, dict), "Basics should be a dict"
    print(f"\n[Test Finnhub] Successfully fetched fundamentals for {symbol}")
    if basics_data:
        print(f"Sample basic (period): {basics_data.get('period')}")
        # print some metric if available, e.g. netMargin
        if 'netMargin' in basics_data:
            print(f"Net Margin: {basics_data['netMargin']}")
