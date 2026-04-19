"""
Bybit 现货数据采集器
"""
import asyncio
import aiohttp
import hashlib
import hmac
import time
from typing import Optional, List, Dict
from core.utils.logger import logger
from core.utils.helpers import safe_execute
from config.api_keys import api_key_manager

BYBIT_API = "https://api.bybit.com"


class BybitSpotCollector:
    """Bybit 现货数据采集"""
    
    def __init__(self):
        self._session = None
        self._rate_limiter = asyncio.Semaphore(5)
        self._api_key = api_key_manager.get("bybit_api_key")
        self._api_secret = api_key_manager.get("bybit_api_secret")
    
    async def _get_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    @safe_execute(default=None)
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    def _sign(self, params: dict) -> str:
        """HMAC SHA256 签名"""
        sorted_params = sorted(params.items())
        message = "&".join([f"{k}={v}" for k, v in sorted_params])
        mac = hmac.new(
            self._api_secret.encode(),
            message.encode(),
            hashlib.sha256
        )
        return mac.hexdigest()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        need_auth: bool = False
    ) -> Optional[dict]:
        await self._rate_limiter.acquire()
        try:
            url = f"{BYBIT_API}{endpoint}"
            params = params or {}
            params["api_key"] = self._api_key
            params["timestamp"] = str(int(time.time() * 1000))
            
            if need_auth and self._api_secret:
                sign = self._sign(params)
                params["sign"] = sign
            
            session = await self._get_session()
            
            if method == "GET":
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("retCode") == 0:
                            return data.get("result", {})
                        else:
                            logger.error(f"Bybit API error: {data.get('retMsg')}")
                            return None
                    else:
                        logger.error(f"Bybit API {resp.status}: {endpoint}")
                        return None
            else:
                async with session.post(url, json=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data if data.get("retCode") == 0 else None
                    else:
                        return None
        except Exception as e:
            logger.error(f"Bybit 请求失败: {e}")
            return None
        finally:
            self._rate_limiter.release()
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 200
    ) -> List[Dict]:
        """获取K线数据"""
        interval_map = {
            "1m": "1", "3m": "3", "5m": "5", "15m": "15",
            "30m": "30", "1h": "60", "4h": "240", "1d": "D",
            "1w": "W", "1M": "M"
        }
        
        params = {
            "category": "spot",
            "symbol": symbol.upper(),
            "interval": interval_map.get(interval, "60"),
            "limit": str(limit),
        }
        
        data = await self._request("GET", "/v5/market/kline", params)
        
        if data and data.get("list"):
            klines = []
            for d in reversed(data["list"]):
                klines.append({
                    "open_time": int(d[0]),
                    "open": float(d[1]),
                    "high": float(d[2]),
                    "low": float(d[3]),
                    "close": float(d[4]),
                    "volume": float(d[5]),
                    "close_time": int(d[0]) + self._interval_to_ms(interval),
                    "quote_volume": float(d[6]) if len(d) > 6 else 0,
                    "trades": int(d[7]) if len(d) > 7 else 0,
                })
            return klines
        return []
    
    def _interval_to_ms(self, interval: str) -> int:
        multipliers = {"m": 60, "h": 3600, "d": 86400, "w": 604800, "M": 2592000}
        unit = interval[-1]
        num = int(interval[:-1]) if interval[:-1] else 1
        return int(num * multipliers.get(unit, 60) * 1000)


_collector = None


def get_collector():
    global _collector
    if _collector is None:
        _collector = BybitSpotCollector()
    return _collector
    async def get_price(self, symbol: str) -> float:
        """获取最新价格"""
        try:
            resp = await self._request("/v5/market/tickers", {"category": "spot", "symbol": f"{symbol.upper()}USDT"})
            if resp and resp.get("data"):
                d = resp["data"][0]
                return float(d.get("last", d.get("close", d.get("price", 0))))
        except Exception:
            pass
        return 0.0
