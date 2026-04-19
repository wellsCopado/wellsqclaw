"""
币安现货数据采集器
"""
import asyncio
import aiohttp
from typing import Optional, List, Dict
from core.utils.logger import logger
from core.utils.helpers import safe_execute

BINANCE_API = "https://api.binance.com"


class BinanceSpotCollector:
    """币安现货数据采集"""

    def __init__(self):
        self._session = None
        self._rate_limiter = asyncio.Semaphore(5)
        logger.info("CryptoMind: Binance现货采集器初始化")

    async def _get_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    @safe_execute(default=None)
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        session = await self._get_session()
        url = f"{BINANCE_API}{endpoint}"
        try:
            async with self._rate_limiter:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.warning(f"Binance API {endpoint}: HTTP {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Binance API error {endpoint}: {e}")
            return None

    async def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[Dict]:
        """获取K线数据"""
        data = await self._request("/api/v3/klines", {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, 1000)
        })
        if not data:
            return []
        return [
            {
                "open_time": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "close_time": k[6],
            }
            for k in data
        ]

    async def get_ticker(self, symbol: str) -> Optional[dict]:
        """获取24小时行情"""
        data = await self._request("/api/v3/ticker/24hr", {"symbol": symbol.upper()})
        if data:
            return {
                "symbol": data["symbol"],
                "last_price": float(data["lastPrice"]),
                "price_change": float(data["priceChange"]),
                "price_change_pct": float(data["priceChangePercent"]) / 100,
                "high_24h": float(data["highPrice"]),
                "low_24h": float(data["lowPrice"]),
                "volume_24h": float(data["volume"]),
                "quote_volume_24h": float(data["quoteVolume"]),
            }
        return None

    async def get_order_book(self, symbol: str, limit: int = 20) -> Optional[dict]:
        """获取订单簿"""
        data = await self._request("/api/v3/depth", {
            "symbol": symbol.upper(),
            "limit": min(limit, 100)
        })
        if data:
            return {
                "bids": [[float(p), float(q)] for p, q in data.get("bids", [])],
                "asks": [[float(p), float(q)] for p, q in data.get("asks", [])],
            }
        return None

    async def get_exchange_info(self) -> dict:
        """获取交易所信息"""
        data = await self._request("/api/v3/exchangeInfo")
        if data:
            return {"symbols": [s["symbol"] for s in data.get("symbols", [])]}
        return {"symbols": []}

    async def get_price(self, symbol: str) -> float:
        """获取最新价格（兼容API）"""
        ticker = await self.get_ticker(symbol)
        if ticker:
            return float(ticker.get("last_price", 0))
        return 0.0
