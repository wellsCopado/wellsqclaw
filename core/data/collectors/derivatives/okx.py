"""OKX 合约/期权数据采集器"""
import time
import hashlib
import requests
from typing import Optional, Dict, Any
from core.utils.helpers import safe_execute
from core.utils.logger import logger


class OKXDerivativesCollector:
    """OKX 衍生品数据采集器（合约/期权）"""

    BASE_URL = "https://www.okx.com"

    def __init__(self, api_key: str = "", api_secret: str = "", passphrase: str = ""):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.passphrase = passphrase or ""
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        logger.info(f"CryptoMind: OKX Derivatives采集器初始化")

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """HMAC SHA256 签名"""
        if not self.api_secret:
            return ""
        message = timestamp + method + path + body
        import hmac, base64
        mac = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).digest()
        return base64.b64encode(mac).decode("utf-8")

    @safe_execute(default={})
    def get_funding_rate(self, inst_id: str = "BTC-USD-SWAP") -> Dict[str, Any]:
        """获取资金费率"""
        path = "/api/v5/public/funding-rate"
        params = {"instId": inst_id}
        try:
            resp = self._session.get(
                f"{self.BASE_URL}{path}",
                params=params,
                timeout=10
            )
            data = resp.json()
            if data.get("code") == "0" and data.get("data"):
                d = data["data"][0]
                return {
                    "symbol": inst_id,
                    "funding_rate": float(d.get("fundingRate", 0)),
                    "next_funding_time": d.get("nextFundingTime", ""),
                    "mark_price": float(d.get("markPrice", 0)),
                }
        except Exception as e:
            logger.error(f"OKX funding rate error: {e}")
        return {}

    @safe_execute(default=[])
    def get_open_interest(self, inst_id: str = "BTC-USD-SWAP") -> list:
        """获取持仓量历史"""
        path = "/api/v5/public/open-interest"
        params = {"instId": inst_id, "limit": "100"}
        try:
            resp = self._session.get(
                f"{self.BASE_URL}{path}",
                params=params,
                timeout=10
            )
            data = resp.json()
            if data.get("code") == "0":
                return [
                    {
                        "inst_id": d["instId"],
                        "oi": float(d.get("oi", 0)),
                        "oi_usd": float(d.get("oiUsd", 0)),
                        "ts": int(d.get("ts", 0)),
                    }
                    for d in data.get("data", [])
                ]
        except Exception as e:
            logger.error(f"OKX OI error: {e}")
        return []

    @safe_execute(default=[])
    def get_tickers(self, inst_type: str = "SWAP") -> list:
        """获取合约Ticker列表"""
        path = "/api/v5/market/tickers"
        params = {"instType": inst_type}
        try:
            resp = self._session.get(
                f"{self.BASE_URL}{path}",
                params=params,
                timeout=10
            )
            data = resp.json()
            if data.get("code") == "0":
                return [
                    {
                        "inst_id": d["instId"],
                        "last": float(d.get("last", 0)),
                        "last_24h_change": float(d.get("last24hPct", 0)) / 100,
                        "volume_24h": float(d.get("vol24h", 0)),
                        "oi": float(d.get("oi", 0)),
                    }
                    for d in data.get("data", [])
                ]
        except Exception as e:
            logger.error(f"OKX tickers error: {e}")
        return []

    @safe_execute(default={})
    def get_mark_price(self, inst_id: str = "BTC-USD-SWAP") -> Dict[str, Any]:
        """获取标记价格"""
        path = "/api/v5/public/mark-price"
        params = {"instId": inst_id}
        try:
            resp = self._session.get(
                f"{self.BASE_URL}{path}",
                params=params,
                timeout=10
            )
            data = resp.json()
            if data.get("code") == "0" and data.get("data"):
                d = data["data"][0]
                return {
                    "inst_id": inst_id,
                    "mark_price": float(d.get("markPx", 0)),
                    "ts": int(d.get("ts", 0)),
                }
        except Exception as e:
            logger.error(f"OKX mark price error: {e}")
        return {}
