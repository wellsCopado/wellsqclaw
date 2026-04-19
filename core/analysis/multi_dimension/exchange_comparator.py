"""
多交易所数据对比分析
对比 Binance / OKX / Bybit 的价格、深度、资金费率、流动性
"""
import asyncio
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from core.utils.logger import logger
from core.utils.helpers import safe_execute


@dataclass
class ExchangePrice:
    """交易所价格快照"""
    exchange: str
    symbol: str
    bid: float     # 买一价
    ask: float     # 卖一价
    spread: float  # 买卖价差
    spread_pct: float  # 价差百分比
    volume_24h: float
    timestamp: int


@dataclass
class ExchangeFunding:
    """交易所资金费率"""
    exchange: str
    symbol: str
    rate: float        # 当前费率
    rate_annual: float # 年化费率
    next_funding: int  # 下次结算时间戳
    predicted: str     # next_funding 预测方向


@dataclass
class ExchangeLiquidity:
    """交易所流动性"""
    exchange: str
    symbol: str
    bid_depth: float   # 买盘深度 (USD)
    ask_depth: float   # 卖盘深度 (USD)
    imbalance: float   # 多空失衡 (1=完美平衡)
    score: float       # 流动性评分 0-100


class ExchangeComparator:
    """
    多交易所数据对比
    发现跨所套利机会、费率差异、流动性分布
    """

    def __init__(self):
        self._collectors = {}
        self._register_collectors()

    def _register_collectors(self):
        """注册各交易所采集器"""
        try:
            from core.data.collectors.spot.binance import BinanceSpotCollector
            self._collectors["Binance"] = BinanceSpotCollector()
        except Exception as e:
            logger.warning(f"Binance采集器注册失败: {e}")

        try:
            from core.data.collectors.spot.okx import OKXSpotCollector
            self._collectors["OKX"] = OKXSpotCollector()
        except Exception as e:
            logger.warning(f"OKX采集器注册失败: {e}")

        try:
            from core.data.collectors.spot.bybit import BybitSpotCollector
            self._collectors["Bybit"] = BybitSpotCollector()
        except Exception as e:
            logger.warning(f"Bybit采集器注册失败: {e}")

    async def get_ticker_snapshot(self, symbol: str) -> Dict[str, ExchangePrice]:
        """获取所有交易所的价格快照"""
        results = {}

        # Binance
        if "Binance" in self._collectors:
            try:
                data = await self._collectors["Binance"].get_ticker(symbol)
                if data:
                    bid, ask = float(data["bid"]), float(data["ask"])
                    spread = ask - bid
                    spread_pct = spread / ask * 100 if ask > 0 else 0
                    results["Binance"] = ExchangePrice(
                        exchange="Binance",
                        symbol=symbol,
                        bid=bid,
                        ask=ask,
                        spread=spread,
                        spread_pct=spread_pct,
                        volume_24h=float(data.get("volume", 0)),
                        timestamp=int(time.time() * 1000),
                    )
            except Exception as e:
                logger.warning(f"Binance行情获取失败: {e}")

        # OKX
        if "OKX" in self._collectors:
            try:
                okx_symbol = symbol.replace("USDT", "-USDT")
                data = await self._collectors["OKX"].get_ticker(okx_symbol)
                if data:
                    bid, ask = float(data["bid"]), float(data["ask"])
                    spread = ask - bid
                    spread_pct = spread / ask * 100 if ask > 0 else 0
                    results["OKX"] = ExchangePrice(
                        exchange="OKX",
                        symbol=symbol,
                        bid=bid,
                        ask=ask,
                        spread=spread,
                        spread_pct=spread_pct,
                        volume_24h=float(data.get("volume", 0)),
                        timestamp=int(time.time() * 1000),
                    )
            except Exception as e:
                logger.warning(f"OKX行情获取失败: {e}")

        # Bybit
        if "Bybit" in self._collectors:
            try:
                data = await self._collectors["Bybit"].get_ticker(symbol)
                if data:
                    bid, ask = float(data["bid"]), float(data["ask"])
                    spread = ask - bid
                    spread_pct = spread / ask * 100 if ask > 0 else 0
                    results["Bybit"] = ExchangePrice(
                        exchange="Bybit",
                        symbol=symbol,
                        bid=bid,
                        ask=ask,
                        spread=spread,
                        spread_pct=spread_pct,
                        volume_24h=float(data.get("volume", 0)),
                        timestamp=int(time.time() * 1000),
                    )
            except Exception as e:
                logger.warning(f"Bybit行情获取失败: {e}")

        return results

    async def get_orderbook_snapshot(
        self, symbol: str, limit: int = 10
    ) -> Dict[str, Dict]:
        """获取所有交易所的订单簿快照"""
        results = {}

        for name, collector in self._collectors.items():
            try:
                if name == "OKX":
                    sym = symbol.replace("USDT", "-USDT")
                else:
                    sym = symbol

                book = await collector.get_order_book(sym, limit=limit)
                if book:
                    # 计算深度
                    bid_depth = sum(float(b[1]) * float(b[0]) for b in book.get("bids", [])[:5])
                    ask_depth = sum(float(a[1]) * float(a[0]) for a in book.get("asks", [])[:5])
                    imbalance = bid_depth / ask_depth if ask_depth > 0 else 1.0

                    results[name] = {
                        "exchange": name,
                        "bid_depth": bid_depth,
                        "ask_depth": ask_depth,
                        "imbalance": imbalance,
                        "score": round(min(bid_depth, ask_depth) / max(bid_depth, ask_depth, 1) * 100, 1),
                        "best_bid": float(book["bids"][0][0]) if book.get("bids") else 0,
                        "best_ask": float(book["asks"][0][0]) if book.get("asks") else 0,
                    }
            except Exception as e:
                logger.warning(f"{name} 订单簿获取失败: {e}")

        return results

    async def compare_prices(self, symbol: str) -> Dict:
        """
        跨所价格对比 + 套利机会检测
        """
        prices = await self.get_ticker_snapshot(symbol)

        if len(prices) < 2:
            return {"error": "需要至少2个交易所数据", "available": list(prices.keys())}

        exchanges = list(prices.keys())

        # 找出最高/最低价
        all_prices = [(name, p) for name, p in prices.items()]
        all_prices.sort(key=lambda x: x[1].ask)

        cheapest_buy = all_prices[0]   # 卖价最低
        most_expensive_sell = all_prices[-1]  # 买价最高

        # 套利空间
        arbitrage = most_expensive_sell[1].bid - cheapest_buy[1].ask
        arbitrage_pct = arbitrage / cheapest_buy[1].ask * 100 if cheapest_buy[1].ask > 0 else 0

        # 流动性排名
        volume_rank = sorted(
            prices.items(),
            key=lambda x: x[1].volume_24h,
            reverse=True
        )

        # 价差排名（越小越好）
        spread_rank = sorted(
            prices.items(),
            key=lambda x: x[1].spread_pct
        )

        return {
            "symbol": symbol,
            "exchanges": len(prices),
            "arbitrage": {
                "opportunity": arbitrage_pct > 0.1,
                "buy_exchange": cheapest_buy[0],
                "buy_price": cheapest_buy[1].ask,
                "sell_exchange": most_expensive_sell[0],
                "sell_price": most_expensive_sell[1].bid,
                "spread_usd": round(arbitrage, 4),
                "spread_pct": round(arbitrage_pct, 4),
                "note": "扣除手续费后实际收益" if arbitrage_pct > 0.1 else "无明显套利空间",
            },
            "volume_ranking": [
                {"exchange": name, "volume_24h": round(p.volume_24h, 2)}
                for name, p in volume_rank
            ],
            "spread_ranking": [
                {"exchange": name, "spread_pct": round(p.spread_pct, 4), "spread_usd": round(p.spread, 4)}
                for name, p in spread_rank
            ],
            "all_prices": {
                name: {
                    "bid": p.bid, "ask": p.ask,
                    "spread_pct": round(p.spread_pct, 4),
                    "volume": round(p.volume_24h, 2),
                }
                for name, p in prices.items()
            },
            "timestamp": int(time.time() * 1000),
        }

    async def compare_funding_rates(self, symbol: str) -> Dict:
        """跨所资金费率对比"""
        try:
            from core.data.collectors.derivatives import get_coinglass_collector
            cg = get_coinglass_collector()

            exchanges_map = {
                "Binance": "Binance",
                "OKX": "OKX",
                "Bybit": "Bybit",
            }

            rates = []
            for ex_name, cg_ex in exchanges_map.items():
                try:
                    data = await cg.get_funding_rate(symbol, exchange=cg_ex)
                    if data and data.get("funding_rate") is not None:
                        rate = float(data["funding_rate"])
                        annual = rate * 3 * 365  # 每8小时一次
                        rates.append({
                            "exchange": ex_name,
                            "rate": rate,
                            "annual_rate": round(annual, 2),
                            "next_funding_time": data.get("next_funding_time", 0),
                            "signal": "做空优于做多" if rate > 0 else "做多优于做空",
                        })
                except Exception as e:
                    logger.debug(f"{ex_name} 资金费率获取失败: {e}")

            if not rates:
                return {"error": "无资金费率数据"}

            rates.sort(key=lambda x: x["rate"])

            # 费率差异套利
            max_rate = max(r["rate"] for r in rates)
            min_rate = min(r["rate"] for r in rates)
            rate_diff = max_rate - min_rate

            return {
                "symbol": symbol,
                "rates": rates,
                "best_for_long": rates[0]["exchange"],  # 费率最低，做多成本最低
                "best_for_short": rates[-1]["exchange"],  # 费率最高，做空收益最高
                "rate_spread_pct": round(rate_diff * 3 * 365, 2),  # 年化差异
                "arbitrage_opportunity": rate_diff > 0.001,  # >0.1%差异有意义
            }
        except Exception as e:
            logger.error(f"资金费率对比失败: {e}")
            return {"error": str(e)}

    async def compare_liquidity(self, symbol: str) -> Dict:
        """跨所流动性对比"""
        books = await self.get_orderbook_snapshot(symbol, limit=10)

        if len(books) < 2:
            return {"error": "需要至少2个交易所数据", "available": list(books.keys())}

        ranking = sorted(books.values(), key=lambda x: x["score"], reverse=True)

        return {
            "symbol": symbol,
            "ranking": ranking,
            "most_liquid": ranking[0]["exchange"] if ranking else None,
            "least_liquid": ranking[-1]["exchange"] if ranking else None,
            "avg_imbalance": round(
                sum(b["imbalance"] for b in books.values()) / len(books), 3
            ),
        }

    async def get_full_comparison(self, symbol: str = "BTCUSDT") -> Dict:
        """
        综合对比报告
        """
        logger.info(f"开始跨所综合对比: {symbol}")

        price_task = self.compare_prices(symbol)
        funding_task = self.compare_funding_rates(symbol)
        liquid_task = self.compare_liquidity(symbol)

        price_r, funding_r, liquid_r = await asyncio.gather(
            price_task, funding_task, liquid_task,
            return_exceptions=True
        )

        # 整体建议
        suggestions = []

        # 费率建议
        if isinstance(funding_r, dict) and "best_for_long" in funding_r:
            suggestions.append({
                "type": "funding",
                "action": f"做多选择 {funding_r['best_for_long']}（费率最低）",
                "detail": f"做空选择 {funding_r['best_for_short']}（费率最高）",
            })

        # 流动性建议
        if isinstance(liquid_r, dict) and "most_liquid" in liquid_r:
            suggestions.append({
                "type": "liquidity",
                "action": f"大额交易用 {liquid_r['most_liquid']}（流动性最好）",
                "detail": f"平均失衡度: {liquid_r.get('avg_imbalance', 'N/A')}",
            })

        # 价格建议
        if isinstance(price_r, dict) and "arbitrage" in price_r:
            arb = price_r["arbitrage"]
            if arb["opportunity"]:
                suggestions.append({
                    "type": "arbitrage",
                    "action": f"跨所套利：买入{arb['buy_exchange']}，卖出{arb['sell_exchange']}",
                    "detail": f"理论收益: {arb['spread_pct']}%（扣除手续费后）",
                })

        return {
            "symbol": symbol,
            "price_comparison": price_r if not isinstance(price_r, Exception) else {"error": str(price_r)},
            "funding_comparison": funding_r if not isinstance(funding_r, Exception) else {"error": str(funding_r)},
            "liquidity_comparison": liquid_r if not isinstance(liquid_r, Exception) else {"error": str(liquid_r)},
            "suggestions": suggestions,
            "timestamp": int(time.time() * 1000),
        }

    @safe_execute(default=None)
    async def close(self):
        """关闭所有采集器"""
        for collector in self._collectors.values():
            if hasattr(collector, "close"):
                await collector.close()


# 便捷函数
async def compare_exchanges(symbol: str = "BTCUSDT") -> Dict:
    """快速对比所有交易所"""
    comp = ExchangeComparator()
    try:
        result = await comp.get_full_comparison(symbol)
        return result
    finally:
        await comp.close()
