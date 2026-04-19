"""CryptoMind Pro Plus AI - 异步工具集"""
import asyncio
import time
import functools
import traceback
from typing import Any, Callable, TypeVar, Coroutine
from core.utils.logger import logger

T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════
# safe_execute — 异常安全装饰器（商用级防护）— 必须在文件顶部定义
# ═══════════════════════════════════════════════════════════════

def safe_execute(default=None, log_level="error"):
    """安全执行装饰器 - 捕获所有异常，防止级联崩溃"""
    def decorator(func):
        log_fn = {
            "error": logger.error,
            "warning": logger.warning,
            "critical": logger.critical,
        }.get(log_level, logger.error)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_fn(f"[safe_execute] {func.__name__} 失败: {type(e).__name__}: {e}")
                logger.debug(f"[safe_execute] {func.__name__} 堆栈:\n{traceback.format_exc()}")
                return default

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_fn(f"[safe_execute] {func.__name__} 失败: {type(e).__name__}: {e}")
                logger.debug(f"[safe_execute] {func.__name__} 堆栈:\n{traceback.format_exc()}")
                return default

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def safe_execute_no_default(log_level="warning"):
    """安全执行装饰器（无默认值版）- 捕获异常并返回 None"""
    def decorator(func):
        log_fn = {
            "error": logger.error,
            "warning": logger.warning,
            "critical": logger.critical,
        }.get(log_level, logger.warning)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_fn(f"[safe_execute] {func.__name__} 失败: {type(e).__name__}: {e}")
                return None

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_fn(f"[safe_execute] {func.__name__} 失败: {type(e).__name__}: {e}")
                return None

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════
# 其他工具函数
# ═══════════════════════════════════════════════════════════════

def timeit(func: Callable) -> Callable:
    """函数执行时间装饰器"""
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.debug(f"{func.__name__} 执行完成: {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error(f"{func.__name__} 执行失败 ({elapsed:.3f}s): {e}")
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.debug(f"{func.__name__} 执行完成: {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error(f"{func.__name__} 执行失败 ({elapsed:.3f}s): {e}")
            raise

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


async def retry_async(
    func: Coroutine,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> T:
    """异步重试机制"""
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await func
        except exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = delay * (backoff ** attempt)
                logger.warning(f"重试 {attempt + 1}/{max_retries}, 等待 {wait_time:.1f}s: {e}")
                await asyncio.sleep(wait_time)
    raise last_exception


def rate_limit(calls_per_second: float):
    """API 调用频率限制装饰器"""
    min_interval = 1.0 / calls_per_second

    def decorator(func):
        last_called = [0.0]

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            elapsed = time.monotonic() - last_called[0]
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            last_called[0] = time.monotonic()
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def format_bytes(size: int) -> str:
    """格式化字节数"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def format_number(n: float, decimals: int = 2) -> str:
    """格式化数字"""
    if abs(n) >= 1e9:
        return f"{n / 1e9:.{decimals}f}B"
    elif abs(n) >= 1e6:
        return f"{n / 1e6:.{decimals}f}M"
    elif abs(n) >= 1e3:
        return f"{n / 1e3:.{decimals}f}K"
    else:
        return f"{n:.{decimals}f}"
