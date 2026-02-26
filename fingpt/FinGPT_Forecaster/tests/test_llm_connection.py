import os
import sys

# 允许从父目录导入 data.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data import client
from dotenv import load_dotenv

load_dotenv()

def test_deepseek_connection():
    model_name = os.environ.get("OPENAI_MODEL", "deepseek/deepseek-chat")
    print(f"Testing connection to OpenRouter using model: {model_name}")
    
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a financial expert."},
                {"role": "user", "content": "Briefly explain the impact of NVIDIA's recent earnings on the AI market."}
            ],
            extra_headers={
                "HTTP-Referer": "https://github.com/FinGPT",
                "X-Title": "FinGPT Test",
            }
        )
        print("\nSuccess! AI Response:")
        print("-" * 30)
        print(completion.choices[0].message.content)
        print("-" * 30)
    except Exception as e:
        print(f"\nFailed to connect to DeepSeek via OpenRouter: {e}")

if __name__ == "__main__":
    test_deepseek_connection()
