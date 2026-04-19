"""
Coinglass API V4 集成 - Hobby Plan ($29/月)
已验证可用端点 (2026-04-18)

可用端点:
- /api/futures/funding-rate/history ✅
- /api/futures/open-interest/history ✅
- /api/futures/liquidation/history ✅
- /api/futures/global-long-short-account-ratio/history ✅
- /api/futures/supported-coins ✅
- /api/futures/supported-exchanges ✅
"""
import asyncio
import time
import aiohttp
from typing import Optional, List, Dict, Tuple
from core.utils.logger import logger
from core.utils.helpers import safe_execute
from config.api_keys import api_key_manager

COINGLASS_BASE_URL = "https://open-api-v4.coinglass.com"


class CoinGlassCollector:
    """Coinglass V4 API 客户端 - 全部使用验证过的端点"""
    
    def __init__(self):
        self.api_key = api_key_manager.get("coinglass_api_key")
        self._session = None
        self._rate_limiter = asyncio.Semaphore(2)
        
        if self.api_key:
            logger.info(f"✅ CoinGlass 已初始化, Key: {self.api_key[:10]}...")
            self.headers = {"CG-API-KEY": self.api_key, "Accept": "application/json"}
        else:
            logger.warning("⚠️ CoinGlass API Key 未配置")
            self.headers = {"Accept": "application/json"}
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    @safe_execute(default=None)
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _fetch(
        self,
        url: str,
        headers: dict = None,
        params: dict = None,
        timeout: float = 30.0
    ) -> Optional[dict]:
        await self._rate_limiter.acquire()
        try:
            session = await self._get_session()
            async with session.get(
                url,
                headers=headers or self.headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                text = await resp.text()
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 429:
                    logger.warning("⚠️ Coinglass 频率超限，暂停5秒")
                    await asyncio.sleep(5)
                    return None
                else:
                    # 打印完整错误以便调试
                    try:
                        err = await resp.json()
                        logger.error(f"Coinglass API {resp.status}: {err.get('msg', text[:200])}")
                    except Exception as e:
                        logger.warning(f"CoinGlass请求异常: {e}")
                        logger.error(f"Coinglass API {resp.status}: {text[:200]}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Coinglass 超时: {url}")
            return None
        except Exception as e:
            logger.error(f"❌ Coinglass 请求失败: {e}")
            return None
        finally:
            self._rate_limiter.release()
    
    @staticmethod
    def _sf(value, default: float = 0.0) -> float:
        """safe_float"""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def _to_usd(value) -> float:
        """转换为 USD"""
        if value is None:
            return 0.0
        try:
            v = float(value)
            return v  # 已经是 USD
        except Exception as e:
            logger.warning(f"CoinGlass请求异常: {e}")
            return 0.0
    
    def _format_symbol(self, symbol: str) -> str:
        """格式化: Coinglass V4 需要 BTCUSDT 格式"""
        symbol = symbol.upper()
        if not symbol.endswith('USDT') and not symbol.endswith('USD'):
            symbol = symbol + 'USDT'
        return symbol
    
    def _extract(self, data) -> Optional[List]:
        """从响应提取 data 列表"""
        if data is None:
            return None
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            code = data.get('code')
            if code not in [0, '0', None]:
                return None  # API 错误已由 _fetch 打印
            for key in ['data', 'result']:
                val = data.get(key)
                if isinstance(val, list):
                    return val
        return None
    
    # ==================== 资金费率历史 ====================
    
    async def get_funding_rate(
        self,
        symbol: str,
        interval: str = "4h",
        lookback_days: int = 30
    ) -> Tuple[List[Dict], int]:
        """
        获取资金费率历史
        interval: 1m, 3m, 5m, 15m, 30m, 1h, 4h, 6h, 8h, 12h, 1d, 1w
        """
        sym = self._format_symbol(symbol)
        total_needed = lookback_days * 6  # 4h 每天6个
        all_data = []
        current_end_time = None
        page = 0
        
        while len(all_data) < total_needed and page < 20:
            limit = min(500, total_needed - len(all_data))
            params = {
                "symbol": sym,
                "exchange": "Binance",
                "interval": interval,
                "limit": limit
            }
            if current_end_time:
                params["endTime"] = current_end_time
            
            data = await self._fetch(
                f"{COINGLASS_BASE_URL}/api/futures/funding-rate/history",
                params=params,
                timeout=10.0
            )
            
            parsed = self._extract(data)
            if not parsed:
                break
            
            # 去重
            if all_data and parsed:
                last_ts = all_data[-1].get('time', 0)
                parsed = [d for d in parsed if d.get('time', 0) != last_ts]
            
            all_data.extend(parsed)
            
            if parsed:
                earliest = min((d.get('time', 0) for d in parsed), default=0)
                current_end_time = earliest - 1
            
            if len(parsed) < limit:
                break
            page += 1
            await asyncio.sleep(0.5)
        
        latest_ts = max((d.get('time', 0) for d in all_data), default=0)
        logger.info(f"  资金费率历史: {len(all_data)} 条 ({sym})")
        return all_data, latest_ts
    
    # ==================== 持仓量历史 ====================
    
    async def get_open_interest(
        self,
        symbol: str,
        interval: str = "4h",
        lookback_days: int = 30
    ) -> Tuple[List[Dict], int]:
        """
        获取持仓量历史
        """
        sym = self._format_symbol(symbol)
        total_needed = lookback_days * 6
        all_data = []
        current_end_time = None
        page = 0
        
        while len(all_data) < total_needed and page < 20:
            limit = min(500, total_needed - len(all_data))
            params = {
                "symbol": sym,
                "exchange": "Binance",
                "interval": interval,
                "limit": limit
            }
            if current_end_time:
                params["endTime"] = current_end_time
            
            data = await self._fetch(
                f"{COINGLASS_BASE_URL}/api/futures/open-interest/history",
                params=params,
                timeout=10.0
            )
            
            parsed = self._extract(data)
            if not parsed:
                break
            
            if all_data and parsed:
                last_ts = all_data[-1].get('time', 0)
                parsed = [d for d in parsed if d.get('time', 0) != last_ts]
            
            all_data.extend(parsed)
            
            if parsed:
                earliest = min((d.get('time', 0) for d in parsed), default=0)
                current_end_time = earliest - 1
            
            if len(parsed) < limit:
                break
            page += 1
            await asyncio.sleep(0.5)
        
        latest_ts = max((d.get('time', 0) for d in all_data), default=0)
        logger.info(f"  持仓量历史: {len(all_data)} 条 ({sym})")
        return all_data, latest_ts
    
    # ==================== 爆仓数据 ====================
    
    async def get_liquidation(self, symbol: str, range_days: int = 7) -> Optional[Dict]:
        """
        获取爆仓统计数据
        """
        sym = self._format_symbol(symbol)
        
        data = await self._fetch(
            f"{COINGLASS_BASE_URL}/api/futures/liquidation/history",
            params={
                "symbol": sym,
                "exchange": "Binance",
                "interval": "4h",
                "limit": min(range_days * 6, 500)
            }
        )
        
        parsed = self._extract(data)
        if not parsed:
            return None
        
        # 24h = 最近 6 个 4h
        recent = parsed[-6:] if len(parsed) >= 6 else parsed
        total_24h = sum(self._to_usd(d.get('long_liquidation_usd', 0)) + 
                       self._to_usd(d.get('short_liquidation_usd', 0)) for d in recent)
        long_24h = sum(self._to_usd(d.get('long_liquidation_usd', 0)) for d in recent)
        short_24h = sum(self._to_usd(d.get('short_liquidation_usd', 0)) for d in recent)
        
        return {
            "symbol": symbol,
            "total_24h_usd": total_24h,
            "long_24h_usd": long_24h,
            "short_24h_usd": short_24h,
            "long_ratio": long_24h / (total_24h + 1),
            "short_ratio": short_24h / (total_24h + 1),
            "history": parsed,
        }
    
    # ==================== 多空比 ====================
    
    async def get_long_short_ratio(self, symbol: str, range_days: int = 7) -> Optional[Dict]:
        """
        获取多空比数据
        """
        sym = self._format_symbol(symbol)
        
        data = await self._fetch(
            f"{COINGLASS_BASE_URL}/api/futures/global-long-short-account-ratio/history",
            params={
                "symbol": sym,
                "exchange": "Binance",
                "interval": "4h",
                "limit": min(range_days * 6, 500)
            }
        )
        
        parsed = self._extract(data)
        if not parsed:
            return None
        
        latest = parsed[-1] if parsed else {}
        return {
            "symbol": symbol,
            "long_percent": self._sf(latest.get('global_account_long_percent')),
            "short_percent": self._sf(latest.get('global_account_short_percent')),
            "long_short_ratio": self._sf(latest.get('global_account_long_short_ratio')),
            "history": parsed,
        }
    
    # ==================== 支持的交易对/交易所查询 ====================
    
    async def get_supported_symbols(self) -> List[str]:
        """获取 Coinglass 支持的币种列表"""
        data = await self._fetch(f"{COINGLASS_BASE_URL}/api/futures/supported-coins")
        parsed = self._extract(data)
        return parsed or []
    
    async def get_supported_exchanges(self) -> List[str]:
        """获取支持的交易所列表"""
        data = await self._fetch(f"{COINGLASS_BASE_URL}/api/futures/supported-exchanges")
        parsed = self._extract(data)
        return parsed or []
    
    # ==================== 综合市场摘要 ====================
    
    async def get_market_summary(self, symbol: str = "BTC") -> dict:
        """获取市场综合摘要 - 一次获取多个指标"""
        sym = self._format_symbol(symbol)
        
        # 并行请求多个数据
        funding_task = self.get_funding_rate(symbol, "4h", 1)
        oi_task = self.get_open_interest(symbol, "4h", 1)
        liq_task = self.get_liquidation(symbol, 1)
        ls_task = self.get_long_short_ratio(symbol, 1)
        
        funding_data, _ = await funding_task
        oi_data, _ = await oi_task
        liq_data = await liq_task
        ls_data = await ls_task
        
        summary = {
            "symbol": symbol,
            "timestamp": int(time.time() * 1000),
        }
        
        # 最新资金费率
        if funding_data:
            latest = funding_data[-1]
            summary["funding_rate"] = {
                "value": self._sf(latest.get('close')),
                "high": self._sf(latest.get('high')),
                "low": self._sf(latest.get('low')),
                "timestamp": latest.get('time'),
            }
        
        # 最新持仓量
        if oi_data:
            latest = oi_data[-1]
            summary["open_interest"] = {
                "value_usd": self._to_usd(latest.get('close')),
                "high_usd": self._to_usd(latest.get('high')),
                "low_usd": self._to_usd(latest.get('low')),
                "timestamp": latest.get('time'),
            }
        
        # 爆仓
        if liq_data:
            summary["liquidation"] = liq_data
        
        # 多空比
        if ls_data:
            summary["long_short"] = ls_data
        
        return summary


# 全局单例
_coinglass_collector = None


def get_coinglass_collector() -> CoinGlassCollector:
    global _coinglass_collector
    if _coinglass_collector is None:
        _coinglass_collector = CoinGlassCollector()
    return _coinglass_collector
