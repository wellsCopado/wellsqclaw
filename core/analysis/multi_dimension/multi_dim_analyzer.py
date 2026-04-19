"""
多维度综合分析器
整合：技术面 + 基本面(衍生品) + 情绪面(新闻) + 链上数据
输出：综合信号 + 置信度 + 风险评级 + 详细因子分解
"""
import asyncio
import time
from typing import Optional
from dataclasses import dataclass
from core.utils.logger import logger
from core.utils.helpers import safe_execute


@dataclass
class MultiDimSignal:
    """多维度综合信号"""
    symbol: str
    timeframe: str
    timestamp: int

    # 综合信号
    signal: str           # BUY / SELL / NEUTRAL
    overall_score: float  # -100 到 +100
    confidence: float     # 0-100
    risk_level: str       # LOW / MEDIUM / HIGH / EXTREME

    # 四维评分
    technical_score: float    # 技术面 -100~+100
    fundamental_score: float  # 基本面 -100~+100
    sentiment_score: float    # 情绪面 -100~+100
    onchain_score: float      # 链上 -100~+100

    # 关键指标快照
    price: float
    rsi: Optional[float]
    macd_signal: str
    trend: str
    funding_rate: float
    news_sentiment: float

    # 信号因子
    bullish_factors: list
    bearish_factors: list
    key_insight: str

    # 知识库增强
    kb_context: str


class MultiDimensionAnalyzer:
    """
    多维度综合分析器

    权重配置：
    - 技术面: 30%
    - 基本面: 30%
    - 情绪面: 20%
    - 链上:   20%
    """

    WEIGHTS = {
        "technical": 0.30,
        "fundamental": 0.30,
        "sentiment": 0.20,
        "onchain": 0.20,
    }

    def __init__(self):
        self._kb = None
        self._validator = None

    def _get_kb(self):
        if self._kb is None:
            try:
                from core.analysis.knowledge_base.knowledge_base import get_knowledge_base
                self._kb = get_knowledge_base()
            except Exception:
                pass
        return self._kb

    # ─────────────────────────────────────────────────────────
    # 技术面评分
    # ─────────────────────────────────────────────────────────
    async def _score_technical(self, symbol: str, timeframe: str) -> tuple[float, dict, list, list]:
        """技术面评分 -100~+100"""
        try:
            from core.analysis.technical.indicators import analyze, technical_to_dict
            from core.data.collectors.spot.binance import BinanceSpotCollector

            b = BinanceSpotCollector()
            klines = await b.get_klines(f"{symbol}USDT", timeframe, 200)
            await b.close()

            if not klines or len(klines) < 30:
                return 0, {}, [], ["K线数据不足"]

            result = analyze(klines, symbol)
            d = technical_to_dict(result)

            # 转换为 -100~+100
            score = d["overall_score"]  # 已经是 -100~+100

            bullish = []
            bearish = []

            if d["rsi"] and d["rsi"] < 35:
                bullish.append(f"RSI超卖({d['rsi']:.0f})")
            elif d["rsi"] and d["rsi"] > 65:
                bearish.append(f"RSI超买({d['rsi']:.0f})")

            if "金叉" in d["macd_signal_text"]:
                bullish.append("MACD金叉")
            elif "死叉" in d["macd_signal_text"]:
                bearish.append("MACD死叉")

            if d["trend"] == "UP":
                bullish.append(f"上升趋势(强度{d['trend_strength']:.0%})")
            elif d["trend"] == "DOWN":
                bearish.append(f"下降趋势(强度{d['trend_strength']:.0%})")

            bb = d["bollinger"]
            if bb.get("price_position_pct") and bb["price_position_pct"] < 20:
                bullish.append("价格接近布林下轨")
            elif bb.get("price_position_pct") and bb["price_position_pct"] > 80:
                bearish.append("价格接近布林上轨")

            return score, d, bullish, bearish

        except Exception as e:
            logger.error(f"技术面评分失败: {e}")
            return 0, {}, [], [f"技术分析错误: {str(e)[:30]}"]

    # ─────────────────────────────────────────────────────────
    # 基本面评分（衍生品数据）
    # ─────────────────────────────────────────────────────────
    async def _score_fundamental(self, symbol: str) -> tuple[float, dict, list, list]:
        """基本面评分 -100~+100"""
        try:
            from core.data.collectors.derivatives import get_coinglass_collector

            cg = get_coinglass_collector()
            data = await cg.get_market_summary(symbol)

            bullish = []
            bearish = []
            score = 0
            count = 0

            # 资金费率
            fr = data.get("funding_rate", {})
            fr_val = fr.get("current_rate", 0)
            if fr_val < -0.05:
                score += 40
                bullish.append(f"资金费率极负({fr_val:.3f}%)")
            elif fr_val < -0.01:
                score += 20
                bullish.append(f"资金费率为负({fr_val:.3f}%)")
            elif fr_val > 0.05:
                score -= 30
                bearish.append(f"资金费率极高({fr_val:.3f}%)")
            elif fr_val > 0.01:
                score -= 10
                bearish.append(f"资金费率偏高({fr_val:.3f}%)")
            count += 1

            # 多空比
            ls = data.get("long_short_ratio", {})
            ls_val = ls.get("ratio", 1.0)
            if ls_val < 0.7:
                score += 20
                bullish.append(f"空头占优(多空比{ls_val:.2f})")
            elif ls_val > 1.5:
                score -= 20
                bearish.append(f"多头过度拥挤(多空比{ls_val:.2f})")
            count += 1

            # 爆仓结构
            liq = data.get("liquidation", {})
            short_liq = liq.get("short_24h", 0)
            long_liq = liq.get("long_24h", 0)
            total_liq = short_liq + long_liq
            if total_liq > 0:
                short_pct = short_liq / total_liq
                if short_pct > 0.7:
                    score += 25
                    bullish.append(f"空头主导爆仓({short_pct:.0%})")
                elif short_pct < 0.3:
                    score -= 25
                    bearish.append(f"多头主导爆仓({1-short_pct:.0%})")
            count += 1

            # 持仓量变化
            oi = data.get("open_interest", {})
            oi_change = oi.get("change_24h_pct", 0)
            if oi_change > 20:
                score -= 10
                bearish.append(f"持仓量急增({oi_change:.1f}%)")
            elif oi_change < -20:
                score += 10
                bullish.append(f"持仓量大幅减少({oi_change:.1f}%)")
            count += 1

            final_score = score / max(count, 1) * 2  # 归一化到 -100~+100
            final_score = max(-100, min(100, final_score))

            return final_score, data, bullish, bearish

        except Exception as e:
            logger.error(f"基本面评分失败: {e}")
            return 0, {}, [], [f"衍生品数据错误: {str(e)[:30]}"]

    # ─────────────────────────────────────────────────────────
    # 情绪面评分（新闻）
    # ─────────────────────────────────────────────────────────
    async def _score_sentiment(self, symbol: str) -> tuple[float, dict, list, list]:
        """情绪面评分 -100~+100"""
        try:
            from core.data.collectors.news.crypto_news import get_news_collector

            news = get_news_collector()
            items = await news.get_latest_news(30)
            summary = news.get_sentiment_summary(items)
            await news.close()

            bullish = []
            bearish = []

            avg_score = summary.get("avg_sentiment_score", 0)
            pos_pct = summary.get("positive_pct", 0)
            neg_pct = summary.get("negative_pct", 0)

            # 转换为 -100~+100
            score = avg_score * 100

            if pos_pct > 60:
                bullish.append(f"新闻情绪偏多({pos_pct:.0f}%看多)")
            elif neg_pct > 50:
                bearish.append(f"新闻情绪偏空({neg_pct:.0f}%看空)")

            # 币种相关新闻
            coin_news = news.filter_by_coin(items, symbol)
            if coin_news:
                coin_summary = news.get_sentiment_summary(coin_news)
                coin_score = coin_summary.get("avg_sentiment_score", 0)
                if coin_score > 0.3:
                    bullish.append(f"{symbol}专项新闻偏多(分数{coin_score:.2f})")
                elif coin_score < -0.3:
                    bearish.append(f"{symbol}专项新闻偏空(分数{coin_score:.2f})")

            return score, summary, bullish, bearish

        except Exception as e:
            logger.error(f"情绪面评分失败: {e}")
            return 0, {}, [], [f"新闻数据错误: {str(e)[:30]}"]

    # ─────────────────────────────────────────────────────────
    # 链上评分
    # ─────────────────────────────────────────────────────────
    async def _score_onchain(self, symbol: str) -> tuple[float, dict, list, list]:
        """链上评分 -100~+100"""
        try:
            bullish = []
            bearish = []
            score = 0

            if symbol in ("BTC", "BITCOIN"):
                from core.data.collectors.onchain.ethereum import get_bitcoin_collector
                btc = get_bitcoin_collector()
                data = await btc.get_full_onchain_data()
                await btc.close()

                mempool = data.get("mempool", {})
                tx_count = mempool.get("tx_count", 0)
                if tx_count > 100000:
                    score -= 10
                    bearish.append(f"Mempool拥堵({tx_count:,}笔)")
                elif tx_count < 20000:
                    score += 10
                    bullish.append(f"Mempool畅通({tx_count:,}笔)")

                large = data.get("large_transfers", [])
                if large:
                    bullish.append(f"检测到{len(large)}笔大额BTC转账")

                return score, data, bullish, bearish

            elif symbol in ("ETH", "ETHEREUM"):
                from core.data.collectors.onchain.ethereum import get_ethereum_collector
                eth = get_ethereum_collector()
                data = await eth.get_full_onchain_data()
                await eth.close()

                gas = data.get("gas", {})
                gas_gwei = gas.get("medium_gwei", 0)
                utilization = gas.get("gas_utilization_pct", 0)

                if utilization > 80:
                    score -= 15
                    bearish.append(f"ETH网络拥堵(利用率{utilization:.0f}%)")
                elif utilization < 40:
                    score += 10
                    bullish.append(f"ETH网络畅通(利用率{utilization:.0f}%)")

                return score, data, bullish, bearish

            else:
                # 其他币种暂无链上数据
                return 0, {}, [], []

        except Exception as e:
            logger.error(f"链上评分失败: {e}")
            return 0, {}, [], []

    # ─────────────────────────────────────────────────────────
    # 综合分析
    # ─────────────────────────────────────────────────────────
    @safe_execute(default=None)
    async def analyze(
        self,
        symbol: str = "BTC",
        timeframe: str = "4h",
        use_kb: bool = True,
    ) -> MultiDimSignal:
        """
        执行完整多维度分析

        Args:
            symbol: 交易对 (BTC/ETH/SOL...)
            timeframe: K线周期 (1h/4h/1d)
            use_kb: 是否使用知识库增强
        """
        logger.info(f"🔬 多维度分析: {symbol} {timeframe}")
        start = time.time()

        # 并行执行四维分析
        tech_task = self._score_technical(symbol, timeframe)
        fund_task = self._score_fundamental(symbol)
        sent_task = self._score_sentiment(symbol)
        onchain_task = self._score_onchain(symbol)

        results = await asyncio.gather(
            tech_task, fund_task, sent_task, onchain_task,
            return_exceptions=True
        )

        # 解包结果
        def safe_unpack(r, default=(0, {}, [], [])):
            if isinstance(r, Exception):
                logger.warning(f"分析维度失败: {r}")
                return default
            return r

        tech_score, tech_data, tech_bull, tech_bear = safe_unpack(results[0])
        fund_score, fund_data, fund_bull, fund_bear = safe_unpack(results[1])
        sent_score, sent_data, sent_bull, sent_bear = safe_unpack(results[2])
        onchain_score, onchain_data, onchain_bull, onchain_bear = safe_unpack(results[3])

        # 加权综合评分
        overall = (
            tech_score * self.WEIGHTS["technical"] +
            fund_score * self.WEIGHTS["fundamental"] +
            sent_score * self.WEIGHTS["sentiment"] +
            onchain_score * self.WEIGHTS["onchain"]
        )
        overall = round(overall, 1)

        # 信号判定
        if overall >= 20:
            signal = "BUY"
        elif overall <= -20:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        # 置信度（基于各维度一致性）
        scores = [tech_score, fund_score, sent_score, onchain_score]
        non_zero = [s for s in scores if s != 0]
        if non_zero:
            same_direction = sum(1 for s in non_zero if (s > 0) == (overall > 0))
            confidence = round(same_direction / len(non_zero) * 100, 1)
        else:
            confidence = 0

        # 风险评级
        abs_score = abs(overall)
        if abs_score >= 60:
            risk_level = "HIGH"
        elif abs_score >= 30:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # 合并因子
        all_bullish = tech_bull + fund_bull + sent_bull + onchain_bull
        all_bearish = tech_bear + fund_bear + sent_bear + onchain_bear

        # 关键洞察
        if signal == "BUY":
            key_insight = f"多维度看多信号: {', '.join(all_bullish[:3])}" if all_bullish else "综合评分偏多"
        elif signal == "SELL":
            key_insight = f"多维度看空信号: {', '.join(all_bearish[:3])}" if all_bearish else "综合评分偏空"
        else:
            key_insight = "多维度信号中性，建议观望"

        # 知识库增强
        kb_context = ""
        if use_kb:
            try:
                kb = self._get_kb()
                if kb:
                    state = {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "signal": signal,
                        "trend": tech_data.get("trend", "SIDEWAYS"),
                        "ema_alignment": "多头排列" if tech_score > 0 else "空头排列",
                        "market_sentiment": "bullish" if sent_score > 0 else "bearish",
                        "rsi_signal": tech_data.get("rsi_signal", "NEUTRAL"),
                    }
                    kb_context = kb.generate_context_prompt(state)
            except Exception as e:
                logger.warning(f"知识库增强失败: {e}")

        # 提取关键指标
        price = 0
        rsi = tech_data.get("rsi")
        macd_signal = tech_data.get("macd_signal_text", "N/A")
        trend = tech_data.get("trend", "SIDEWAYS")
        funding_rate = 0
        news_sentiment = sent_data.get("avg_sentiment_score", 0)

        try:
            fr_data = fund_data.get("funding_rate", {})
            funding_rate = fr_data.get("current_rate", 0)
        except Exception:
            pass

        elapsed = round(time.time() - start, 2)
        logger.info(
            f"✅ 多维度分析完成 ({elapsed}s): {symbol} {signal} "
            f"综合={overall} 置信={confidence}% 风险={risk_level}"
        )

        return MultiDimSignal(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=int(time.time() * 1000),
            signal=signal,
            overall_score=overall,
            confidence=confidence,
            risk_level=risk_level,
            technical_score=round(tech_score, 1),
            fundamental_score=round(fund_score, 1),
            sentiment_score=round(sent_score, 1),
            onchain_score=round(onchain_score, 1),
            price=price,
            rsi=rsi,
            macd_signal=macd_signal,
            trend=trend,
            funding_rate=funding_rate,
            news_sentiment=news_sentiment,
            bullish_factors=all_bullish[:5],
            bearish_factors=all_bearish[:5],
            key_insight=key_insight,
            kb_context=kb_context,
        )

    def to_dict(self, sig: MultiDimSignal) -> dict:
        return {
            "symbol": sig.symbol,
            "timeframe": sig.timeframe,
            "timestamp": sig.timestamp,
            "signal": sig.signal,
            "overall_score": sig.overall_score,
            "confidence": sig.confidence,
            "risk_level": sig.risk_level,
            "dimensions": {
                "technical": sig.technical_score,
                "fundamental": sig.fundamental_score,
                "sentiment": sig.sentiment_score,
                "onchain": sig.onchain_score,
            },
            "market": {
                "price": sig.price,
                "rsi": sig.rsi,
                "macd": sig.macd_signal,
                "trend": sig.trend,
                "funding_rate": sig.funding_rate,
                "news_sentiment": sig.news_sentiment,
            },
            "bullish_factors": sig.bullish_factors,
            "bearish_factors": sig.bearish_factors,
            "key_insight": sig.key_insight,
            "kb_context": sig.kb_context[:200] if sig.kb_context else "",
        }


_analyzer: Optional[MultiDimensionAnalyzer] = None


def get_multi_dim_analyzer() -> MultiDimensionAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = MultiDimensionAnalyzer()
    return _analyzer
