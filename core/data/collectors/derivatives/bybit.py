"""Bybit 合约数据采集器"""
import requests
from typing import Optional, Dict, Any
from core.utils.helpers import safe_execute
from core.utils.logger import logger


class BybitDerivativesCollector:
    """Bybit 线性/反向合约数据采集器"""

    BASE_URL = "https://api.bybit.com"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        logger.info(f"CryptoMind: Bybit Derivatives采集器初始化")

    @safe_execute(default={})
    def get_funding_rate(self, category: str = "linear", symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """获取资金费率"""
        path = "/v5/market/funding/history"
        params = {"category": category, "symbol": symbol, "limit": 1}
        try:
            resp = self._session.get(
                f"{self.BASE_URL}{path}",
                params=params,
                timeout=10
            )
            data = resp.json()
            if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                d = data["result"]["list"][0]
                return {
                    "symbol": symbol,
                    "category": category,
                    "funding_rate": float(d.get("fundingRate", 0)),
                    "funding_time": d.get("fundingTime", ""),
                }
        except Exception as e:
            logger.error(f"Bybit funding rate error: {e}")
        return {}

    @safe_execute(default=[])
    def get_open_interest(self, category: str = "linear", symbol: str = "BTCUSDT") -> list:
        """获取持仓量历史"""
        path = "/v5/market/open-interest"
        params = {"category": category, "symbol": symbol, "limit": 50}
        try:
            resp = self._session.get(
                f"{self.BASE_URL}{path}",
                params=params,
                timeout=10
            )
            data = resp.json()
            if data.get("retCode") == 0:
                return [
                    {
                        "symbol": symbol,
                        "category": category,
                        "oi": float(d.get("openInterest", 0)),
                        "ts": int(d.get("timestamp", 0)),
                    }
                    for d in data.get("result", {}).get("list", [])
                ]
        except Exception as e:
            logger.error(f"Bybit OI error: {e}")
        return []

    @safe_execute(default=[])
    def get_tickers(self, category: str = "linear") -> list:
        """获取合约Ticker"""
        path = "/v5/market/tickers"
        params = {"category": category}
        try:
            resp = self._session.get(
                f"{self.BASE_URL}{path}",
                params=params,
                timeout=10
            )
            data = resp.json()
            if data.get("retCode") == 0:
                return [
                    {
                        "symbol": d["symbol"],
                        "last": float(d.get("lastPrice", 0)),
                        "change_24h": float(d.get("price24hPcnt", 0)),
                        "volume_24h": float(d.get("volume24h", 0)),
                        "oi": float(d.get("openInterest", 0)),
                    }
                    for d in data.get("result", {}).get("list", [])
                ]
        except Exception as e:
            logger.error(f"Bybit tickers error: {e}")
        return []

    @safe_execute(default={})
    def get_liquidations(self, category: str = "linear", symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """获取近期爆仓数据"""
        path = "/v5/market/liquidations"
        params = {"category": category, "symbol": symbol, "limit": 20}
        try:
            resp = self._session.get(
                f"{self.BASE_URL}{path}",
                params=params,
                timeout=10
            )
            data = resp.json()
            if data.get("retCode") == 0:
                liqs = data.get("result", {}).get("list", [])
                total_long = sum(float(d["size"]) for d in liqs if d.get("side", "").upper() == "BUY")
                total_short = sum(float(d["size"]) for d in liqs if d.get("side", "").upper() == "SELL")
                return {
                    "symbol": symbol,
                    "liquidations_long_24h": total_long,
                    "liquidations_short_24h": total_short,
                    "count": len(liqs),
                }
        except Exception as e:
            logger.error(f"Bybit liquidations error: {e}")
        return {}
