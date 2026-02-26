import pytest
import os
import time
from rate_limiter import RateLimiter, cache

def test_rate_limiter_basic():
    """测试基础频控功能"""
    service_name = "test_basic"
    # 清理旧数据
    cache.delete(f"rate_limit:{service_name}")
    
    limiter = RateLimiter(service_name, max_calls=2, period_seconds=2)
    
    start_time = time.time()
    
    # 前两次应该瞬间完成
    limiter.wait_if_needed()
    limiter.wait_if_needed()
    
    elapsed = time.time() - start_time
    assert elapsed < 1.0, f"前两次调用不应等待过久: {elapsed:.2f}s"
    
    # 第三次应该触发等待
    limiter.wait_if_needed()
    elapsed = time.time() - start_time
    assert elapsed >= 1.5, f"第三次调用应触发等待: {elapsed:.2f}s"

def test_rate_limiter_persistence():
    """测试频控状态的持久化（模拟 LevelDB 功能）"""
    service_name = "test_persist"
    cache.delete(f"rate_limit:{service_name}")
    
    limiter1 = RateLimiter(service_name, max_calls=1, period_seconds=5)
    limiter1.wait_if_needed() # 消耗一次配额
    
    # 创建新对象，模拟重启或多进程
    limiter2 = RateLimiter(service_name, max_calls=1, period_seconds=5)
    
    start_time = time.time()
    limiter2.wait_if_needed() # 应该等待
    elapsed = time.time() - start_time
    assert elapsed >= 4.0, f"持久化状态应生效，第二次调用需等待: {elapsed:.2f}s"
