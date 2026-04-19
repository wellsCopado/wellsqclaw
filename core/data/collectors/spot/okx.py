"""
OKX 现货数据采集器
"""
import asyncio
import aiohttp
import hashlib
import hmac
import base64
import time
from typing import Optional, List, Dict
from core.utils.logger import logger
from core.utils.helpers import safe_execute
from config.api_keys import api_key_manager

OKX_API = "https://www.okx.com"


class OKXSpotCollector:
    """OKX 现货数据采集"""
    
    def __init__(self):
        self._session = None
        self._rate_limiter = asyncio.Semaphore(5)
        self._api_key = api_key_manager.get("okx_api_key")
        self._api_secret = api_key_manager.get("okx_api_secret")
        self._passphrase = api_key_manager.get("okx_passphrase")
    
    async def _get_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    @safe_execute(default=None)
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    def _sign(self, message: str) -> str:
        """HMAC SHA256 签名"""
        mac = hmac.new(
            self._api_secret.encode(),
            message.encode(),
            hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        need_auth: bool = False
    ) -> Optional[dict]:
        await self._rate_limiter.acquire()
        try:
            url = f"{OKX_API}{endpoint}"
            headers = {"Content-Type": "application/json"}
            
            if need_auth and self._api_key:
                timestamp = str(time.time())
                message = timestamp + method + endpoint
                if params:
                    import json as json_module
                    message += json_module.dumps(params)
                sign = self._sign(message)
                headers.update({
                    "OKX-API-KEY": self._api_key,
                    "OKX-SIGN": sign,
                    "OKX-TIMESTAMP": timestamp,
                    "OKX-PASSPHRASE": self._passphrase,
                    "OKX-API-KEY-TYPE": "0",
                })
            
            session = await self._get_session()
            async with session.request(
                method, url, json=params if method in ["POST", "PUT"] else None,
                params=params if method == "GET" else None,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("code") == "0":
                        return data.get("data", [])
                    else:
                        logger.error(f"OKX API error: {data.get('msg')}")
                        return None
                else:
                    logger.error(f"OKX API {resp.status}: {endpoint}")
                    return None
        except Exception as e:
            logger.error(f"OKX 请求失败: {e}")
            return None
        finally:
            self._rate_limiter.release()
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100
    ) -> List[Dict]:
        """获取K线数据"""
        # OKX symbol 格式: BTC-USDT
        okx_symbol = symbol.replace("USDT", "-USDT")
        bar = interval.replace("m", "m").replace("h", "H").replace("d", "D")
        
        params = {
            "instId": okx_symbol,
            "bar": bar,
            "limit": str(limit),
        }
        
        data = await self._request("GET", "/api/v5/market/history-candles", params)
        
        if data:
            klines = []
            for d in data:
                klines.append({
                    "open_time": int(d[0]),
                    "open": float(d[1]),
                    "high": float(d[2]),
                    "low": float(d[3]),
                    "close": float(d[4]),
                    "volume": float(d[5]),
                    "close_time": int(d[0]) + self._bar_to_ms(bar),
                    "quote_volume": float(d[7]) if len(d) > 7 else 0,
                    "trades": int(d[8]) if len(d) > 8 else 0,
                })
            return klines
        return []
    
    def _bar_to_ms(self, bar: str) -> int:
        """时间粒度转毫秒"""
        multipliers = {"m": 60, "H": 3600, "D": 86400, "W": 604800, "M": 2592000}
        unit = bar[-1]
        num = int(bar[:-1]) if bar[:-1] else 1
        return int(num * multipliers.get(unit, 60) * 1000)


_collector = None


def get_collector():
    global _collector
    if _collector is None:
        _collector = OKXSpotCollector()
    return _collector
    async def get_price(self, symbol: str) -> float:
        """获取最新价格"""
        try:
            if "binance" in "/Users/wells/Desktop/crypto/CryptoMindProPlusAI/core/data/collectors/spot/okx.py":
                return await self.get_ticker(symbol).get("last_price", 0)
            resp = await self._request("/api/v5/market/ticker", {"instId": f"{symbol}-USDT"})
            if resp and resp.get("data"):
                d = resp["data"][0]
                return float(d.get("last", d.get("close", 0)))
        except Exception:
            pass
        return 0.0
