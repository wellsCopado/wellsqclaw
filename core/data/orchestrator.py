"""
数据采集总调度器 - 增强版
整合现货、衍生品、链上、新闻四大数据源
支持：定时任务 + 队列管理 + 错误重试 + 降级策略
"""
import asyncio
import time
import hashlib
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from core.utils.logger import logger
from core.utils.helpers import safe_execute


# ─────────────────────────────────────────────────────────────
# 调度配置
# ─────────────────────────────────────────────────────────────
@dataclass
class CollectionTask:
    """采集任务定义"""
    name: str                    # 任务唯一名称
    source: str                  # 数据源: spot/derivatives/onchain/news
    exchange: str = ""            # 交易所
    symbol: str = "BTC"          # 交易对
    interval: str = "1h"         # 时间周期
    collector_method: str = ""   # 采集方法名
    collector_args: tuple = ()   # 采集参数
    collector_kwargs: dict = field(default_factory=dict)
    retry: int = 3               # 重试次数
    timeout: float = 30.0        # 超时秒数
    priority: int = 0            # 优先级(越大越高)


@dataclass
class CollectionResult:
    """采集结果"""
    task_name: str
    success: bool
    data: Any = None
    error: str = ""
    duration_ms: float = 0
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0


class DataOrchestrator:
    """
    数据采集总调度器
    
    功能：
    1. 统一管理现货/衍生品/链上/新闻四大数据源
    2. 支持并行/串行/优先级采集
    3. 内置错误重试和降级策略
    4. 定时任务调度
    5. 采集状态追踪
    """
    
    # 现货交易所列表
    SPOT_EXCHANGES = ["binance", "okx", "bybit"]
    # 默认采集币种
    DEFAULT_SYMBOLS = ["BTC", "ETH"]
    # 默认采集周期
    DEFAULT_INTERVALS = ["1h", "4h", "1d"]
    
    def __init__(self):
        # ── 现货采集器 ──
        from core.data.collectors.spot.binance import BinanceSpotCollector
        from core.data.collectors.spot.okx import OKXSpotCollector
        from core.data.collectors.spot.bybit import BybitSpotCollector
        self.spot_collectors = {
            "binance": BinanceSpotCollector(),
            "okx": OKXSpotCollector(),
            "bybit": BybitSpotCollector(),
        }
        
        # ── 衍生品采集器 ──
        from core.data.collectors.derivatives import get_coinglass_collector
        self.derivatives = get_coinglass_collector()
        
        # ── 链上采集器 (延迟导入，待创建) ──
        self._onchain_collectors = {}
        
        # ── 新闻采集器 (延迟导入，待创建) ──
        self._news_collector = None
        
        # ── 调度状态 ──
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._last_collection_time: dict[str, float] = {}
        self._collection_stats: dict[str, dict] = {}
        self._failed_tasks: dict[str, int] = {}  # task_name -> fail_count
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        
        # ── 采集任务注册表 ──
        self._tasks: dict[str, CollectionTask] = {}
        self._task_handlers: dict[str, Callable] = {}
        
        # ── 初始化默认任务 ──
        self._register_default_tasks()
        
        # ── 注册链上采集器 ──
        try:
            from core.data.collectors.onchain.ethereum import get_ethereum_collector, get_bitcoin_collector
            self._onchain_collectors = {
                'ethereum': get_ethereum_collector(),
                'bitcoin': get_bitcoin_collector(),
            }
            logger.info('链上采集器已注册: ethereum, bitcoin')
        except Exception as e:
            logger.warning(f'链上采集器注册失败: {e}')
        
        # ── 注册新闻采集器 ──
        try:
            from core.data.collectors.news.crypto_news import get_news_collector
            self._news_collector = get_news_collector()
            logger.info('新闻采集器已注册')
        except Exception as e:
            logger.warning(f'新闻采集器注册失败: {e}')
        # ── 现货采集器 ──
        from core.data.collectors.spot.binance import BinanceSpotCollector
        from core.data.collectors.spot.okx import OKXSpotCollector
        from core.data.collectors.spot.bybit import BybitSpotCollector
        self.spot_collectors = {
            "binance": BinanceSpotCollector(),
            "okx": OKXSpotCollector(),
            "bybit": BybitSpotCollector(),
        }
        
        # ── 衍生品采集器 ──
        from core.data.collectors.derivatives import get_coinglass_collector
        self.derivatives = get_coinglass_collector()
        
        # ── 链上采集器 (延迟导入，待创建) ──
        self._onchain_collectors = {}
        
        # ── 新闻采集器 (延迟导入，待创建) ──
        self._news_collector = None
        
        # ── 调度状态 ──
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._last_collection_time: dict[str, float] = {}
        self._collection_stats: dict[str, dict] = {}
        self._failed_tasks: dict[str, int] = {}  # task_name -> fail_count
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        
        # ── 采集任务注册表 ──
        self._tasks: dict[str, CollectionTask] = {}
        self._task_handlers: dict[str, Callable] = {}
        
        # ── 初始化默认任务 ──
        self._register_default_tasks()
    
    def _register_default_tasks(self):
        """注册默认采集任务"""
        # 现货K线任务
        for ex in self.SPOT_EXCHANGES:
            for sym in self.DEFAULT_SYMBOLS:
                for intv in ["1h", "4h", "1d"]:
                    name = f"spot_{ex}_{sym}_{intv}"
                    self._tasks[name] = CollectionTask(
                        name=name,
                        source="spot",
                        exchange=ex,
                        symbol=sym,
                        interval=intv,
                        collector_method="get_klines",
                        collector_args=(f"{sym}USDT", intv, 1000 if intv != "1d" else 365),
                        retry=3,
                        timeout=20.0,
                        priority=1,
                    )
        
        # 衍生品任务
        for sym in self.DEFAULT_SYMBOLS:
            for method in ["get_funding_rate", "get_open_interest", "get_liquidation", "get_long_short_ratio"]:
                name = f"deriv_{sym}_{method}"
                args = (sym, "4h" if method != "get_liquidation" else 1)
                if method == "get_liquidation":
                    args = (sym, 1)
                elif method == "get_long_short_ratio":
                    args = (sym, 1)
                self._tasks[name] = CollectionTask(
                    name=name,
                    source="derivatives",
                    symbol=sym,
                    collector_method=method,
                    collector_args=args,
                    retry=3,
                    timeout=30.0,
                    priority=2,
                )
    
    # ── 采集器访问 ──
    def get_spot_collector(self, exchange: str):
        return self.spot_collectors.get(exchange)
    
    def get_derivatives_collector(self):
        return self.derivatives
    
    def register_onchain_collector(self, chain: str, collector):
        """注册链上采集器"""
        self._onchain_collectors[chain] = collector
        logger.info(f"注册链上采集器: {chain}")
    
    def register_news_collector(self, collector):
        """注册新闻采集器"""
        self._news_collector = collector
        logger.info("注册新闻采集器")
    
    def register_task(self, task: CollectionTask, handler: Callable):
        """注册自定义采集任务"""
        self._tasks[task.name] = task
        self._task_handlers[task.name] = handler
    
    # ── 核心采集逻辑 ──
    async def _execute_task(self, task: CollectionTask) -> CollectionResult:
        """执行单个采集任务"""
        start = time.perf_counter()
        last_err = ""
        
        for attempt in range(task.retry):
            try:
                # 现货采集
                if task.source == "spot":
                    collector = self.spot_collectors.get(task.exchange)
                    if not collector:
                        return CollectionResult(task.name, False, error=f"未知的交易所: {task.exchange}")
                    method = getattr(collector, task.collector_method)
                    data = await asyncio.wait_for(
                        method(*task.collector_args, **task.collector_kwargs),
                        timeout=task.timeout
                    )
                    self._failed_tasks.pop(task.name, None)
                    return CollectionResult(
                        task_name=task.name,
                        success=True,
                        data=data,
                        duration_ms=(time.perf_counter() - start) * 1000,
                        retry_count=attempt,
                    )
                
                # 衍生品采集
                elif task.source == "derivatives":
                    method = getattr(self.derivatives, task.collector_method)
                    data = await asyncio.wait_for(
                        method(*task.collector_args, **task.collector_kwargs),
                        timeout=task.timeout
                    )
                    self._failed_tasks.pop(task.name, None)
                    return CollectionResult(
                        task_name=task.name,
                        success=True,
                        data=data,
                        duration_ms=(time.perf_counter() - start) * 1000,
                        retry_count=attempt,
                    )
                
                # 链上采集
                elif task.source == "onchain":
                    chain = task.collector_kwargs.get("chain", "ethereum")
                    collector = self._onchain_collectors.get(chain)
                    if not collector:
                        return CollectionResult(task.name, False, error=f"未知的链: {chain}")
                    method = getattr(collector, task.collector_method)
                    data = await asyncio.wait_for(
                        method(*task.collector_args, **task.collector_kwargs),
                        timeout=task.timeout
                    )
                    self._failed_tasks.pop(task.name, None)
                    return CollectionResult(
                        task_name=task.name,
                        success=True,
                        data=data,
                        duration_ms=(time.perf_counter() - start) * 1000,
                        retry_count=attempt,
                    )
                
                # 新闻采集
                elif task.source == "news":
                    if not self._news_collector:
                        return CollectionResult(task.name, False, error="新闻采集器未注册")
                    method = getattr(self._news_collector, task.collector_method)
                    data = await asyncio.wait_for(
                        method(*task.collector_args, **task.collector_kwargs),
                        timeout=task.timeout
                    )
                    self._failed_tasks.pop(task.name, None)
                    return CollectionResult(
                        task_name=task.name,
                        success=True,
                        data=data,
                        duration_ms=(time.perf_counter() - start) * 1000,
                        retry_count=attempt,
                    )
                
            except asyncio.TimeoutError:
                last_err = f"超时 (attempt {attempt+1}/{task.retry})"
                logger.warning(f"[{task.name}] 超时: {task.timeout}s")
            except Exception as e:
                last_err = str(e)
                logger.warning(f"[{task.name}] 采集失败: {e}")
                await asyncio.sleep(1 * (attempt + 1))  # 递增等待
        
        # 所有重试均失败
        self._failed_tasks[task.name] = self._failed_tasks.get(task.name, 0) + 1
        return CollectionResult(
            task_name=task.name,
            success=False,
            error=last_err,
            duration_ms=(time.perf_counter() - start) * 1000,
            retry_count=task.retry,
        )
    
    # ── 并行采集 ──
    async def collect_parallel(
        self,
        task_names: list[str] = None,
        source: str = None,
        timeout_per_task: float = 30.0,
    ) -> dict[str, CollectionResult]:
        """
        并行执行多个采集任务
        
        Args:
            task_names: 指定任务名列表，为空则采集所有
            source: 筛选数据源 (spot/derivatives/onchain/news)
            timeout_per_task: 每个任务超时
        """
        # 确定要执行的任务
        if task_names:
            tasks_to_run = [self._tasks[n] for n in task_names if n in self._tasks]
        elif source:
            tasks_to_run = [t for t in self._tasks.values() if t.source == source]
        else:
            tasks_to_run = list(self._tasks.values())
        
        if not tasks_to_run:
            logger.warning("没有可执行的采集任务")
            return {}
        
        logger.info(f"并行采集 {len(tasks_to_run)} 个任务...")
        
        # 并发执行
        coros = [self._execute_task(t) for t in tasks_to_run]
        results = await asyncio.gather(*coros, return_exceptions=True)
        
        # 整理结果
        output = {}
        success_count = 0
        for task, result in zip(tasks_to_run, results):
            if isinstance(result, Exception):
                output[task.name] = CollectionResult(
                    task_name=task.name,
                    success=False,
                    error=str(result),
                )
            else:
                output[task.name] = result
                if result.success:
                    success_count += 1
                    self._last_collection_time[task.name] = result.timestamp
        
        # 更新统计
        self._update_stats(output)
        
        logger.info(f"并行采集完成: {success_count}/{len(tasks_to_run)} 成功")
        return output
    
    # ── 定时调度 ──
    async def _scheduler_loop(self, interval_seconds: int = 300):
        """定时调度循环（每5分钟全量采集一次）"""
        logger.info(f"调度器启动，周期: {interval_seconds}秒")
        while self._running:
            try:
                # 优先采集失败过的任务
                failed_names = list(self._failed_tasks.keys())
                if failed_names:
                    logger.info(f"优先重试失败任务: {failed_names}")
                
                # 全量并行采集
                await self.collect_parallel()
                
                # 等待下一个周期
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"调度循环异常: {e}")
                await asyncio.sleep(60)
    
    def start_scheduler(self, interval_seconds: int = 300):
        """启动后台定时调度"""
        if self._running:
            logger.warning("调度器已在运行")
            return
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop(interval_seconds))
        logger.info(f"定时调度已启动 (每{interval_seconds}秒)")
    
    async def stop_scheduler(self):
        """停止定时调度"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("定时调度已停止")
    
    # ── 状态查询 ──
    def get_status(self) -> dict:
        """获取调度器状态"""
        return {
            "running": self._running,
            "total_tasks": len(self._tasks),
            "failed_tasks": dict(self._failed_tasks),
            "last_collection": {
                k: datetime.fromtimestamp(v).strftime("%H:%M:%S")
                for k, v in self._last_collection_time.items()
            },
            "stats": self._collection_stats,
            "sources": {
                "spot": len([t for t in self._tasks.values() if t.source == "spot"]),
                "derivatives": len([t for t in self._tasks.values() if t.source == "derivatives"]),
                "onchain": len([t for t in self._tasks.values() if t.source == "onchain"]),
                "news": len([t for t in self._tasks.values() if t.source == "news"]),
            },
        }
    
    def get_failed_tasks(self) -> list[str]:
        """获取失败任务列表"""
        return list(self._failed_tasks.keys())
    
    def _update_stats(self, results: dict[str, CollectionResult]):
        """更新统计"""
        for name, result in results.items():
            if name not in self._collection_stats:
                self._collection_stats[name] = {
                    "total": 0, "success": 0, "fail": 0, "avg_ms": 0, "total_ms": 0
                }
            s = self._collection_stats[name]
            s["total"] += 1
            if result.success:
                s["success"] += 1
                s["total_ms"] += result.duration_ms
                s["avg_ms"] = s["total_ms"] / s["success"]
            else:
                s["fail"] += 1
    
    # ── 快捷采集方法 ──
    async def collect_spot_klines(
        self, exchange: str, symbol: str, interval: str, limit: int = 1000
    ):
        """采集现货K线（单次）"""
        task = CollectionTask(
            name=f"spot_{exchange}_{symbol}_{interval}",
            source="spot",
            exchange=exchange,
            symbol=symbol,
            interval=interval,
            collector_method="get_klines",
            collector_args=(f"{symbol}USDT", interval, limit),
        )
        result = await self._execute_task(task)
        if result.success:
            self._last_collection_time[task.name] = result.timestamp
        return result
    
    async def collect_derivatives_summary(self, symbol: str = "BTC") -> dict:
        """采集衍生品综合数据"""
        task_names = [
            f"deriv_{symbol}_get_funding_rate",
            f"deriv_{symbol}_get_open_interest",
            f"deriv_{symbol}_get_liquidation",
            f"deriv_{symbol}_get_long_short_ratio",
        ]
        results = await self.collect_parallel(task_names)
        
        summary = {}
        for name, result in results.items():
            if result.success:
                key = name.replace(f"deriv_{symbol}_", "")
                summary[key] = result.data
        
        # 获取市场摘要
        try:
            summary["market_summary"] = await self.derivatives.get_market_summary(symbol)
        except Exception as e:
            logger.warning(f"获取市场摘要失败: {e}")
        
        return summary
    
    async def collect_full_for_analysis(self, symbol: str = "BTC") -> dict:
        """
        采集完整分析数据（所有数据源）
        这是最重要的采集入口
        """
        logger.info(f"开始采集 {symbol} 全维度数据...")
        
        # 并行采集所有任务
        all_results = await self.collect_parallel()
        
        # 整理现货K线
        klines = {
            "1h": all_results.get(f"spot_binance_{symbol}_1h"),
            "4h": all_results.get(f"spot_binance_{symbol}_4h"),
            "1d": all_results.get(f"spot_binance_{symbol}_1d"),
        }
        
        # 整理衍生品数据
        deriv = {
            "funding_rate": all_results.get(f"deriv_{symbol}_get_funding_rate"),
            "open_interest": all_results.get(f"deriv_{symbol}_get_open_interest"),
            "liquidation": all_results.get(f"deriv_{symbol}_get_liquidation"),
            "long_short": all_results.get(f"deriv_{symbol}_get_long_short_ratio"),
        }
        
        # 统计
        total = len(all_results)
        success = sum(1 for r in all_results.values() if r.success)
        
        return {
            "symbol": symbol,
            "timestamp": int(time.time() * 1000),
            "stats": {"total": total, "success": success, "fail": total - success},
            "spot_klines": {k: r.data if r.success else None for k, r in klines.items()},
            "derivatives": {k: r.data if r.success else None for k, r in deriv.items()},
            "failed_tasks": [n for n, r in all_results.items() if not r.success],
        }
    
    # ── 清理 ──
    @safe_execute(default=None)
    async def close(self):
        """关闭所有采集器"""
        await self.stop_scheduler()
        for collector in self.spot_collectors.values():
            if hasattr(collector, 'close'):
                await collector.close()
        await self.derivatives.close()
        
        # 关闭链上采集器
        for c in self._onchain_collectors.values():
            if hasattr(c, 'close'):
                await c.close()
        
        # 关闭新闻采集器
        if self._news_collector and hasattr(self._news_collector, 'close'):
            await self._news_collector.close()
        
        logger.info("数据编排器已关闭")


# ─────────────────────────────────────────────────────────────
# 全局单例
# ─────────────────────────────────────────────────────────────
_orchestrator: Optional[DataOrchestrator] = None


def get_orchestrator() -> DataOrchestrator:
    """获取数据编排器单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = DataOrchestrator()
    return _orchestrator
