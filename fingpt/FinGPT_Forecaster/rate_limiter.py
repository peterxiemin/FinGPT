import time
from diskcache import Cache
import os

# 初始化全局缓存目录，模拟 LevelDB 的持久化kv存储
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".rate_limit_cache")
cache = Cache(CACHE_DIR)

class RateLimiter:
    """
    基于磁盘缓存的全局频控器（支持多进程）
    """
    def __init__(self, service_name, max_calls, period_seconds):
        self.service_name = service_name
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self.key = f"rate_limit:{service_name}"

    def wait_if_needed(self):
        """
        检查并强制等待，直到满足频控要求
        """
        while True:
            now = time.time()
            # 获取该服务的调用时间戳列表
            calls = cache.get(self.key, default=[])
            
            # 清理过期的调用记录
            calls = [t for t in calls if now - t < self.period_seconds]
            
            if len(calls) < self.max_calls:
                # 允许调用，记录当前时间
                calls.append(now)
                cache.set(self.key, calls)
                return
            
            # 达到上限，计算需要等待的时间
            sleep_time = self.period_seconds - (now - calls[0])
            if sleep_time > 0:
                print(f"[RateLimiter] {self.service_name} reached limit. Sleeping {sleep_time:.2f}s...")
                time.sleep(sleep_time)
            
# 预定义各个服务的限制
# Finnhub Free Tier: 30 calls/minute (平均 1次/2秒)
# yfinance: 虽无明确限制，但高频请求易被封IP，建议 1次/1秒
finnhub_limiter = RateLimiter("finnhub", max_calls=30, period_seconds=60)
yfinance_limiter = RateLimiter("yfinance", max_calls=1, period_seconds=1)
openrouter_limiter = RateLimiter("openrouter", max_calls=50, period_seconds=60)
