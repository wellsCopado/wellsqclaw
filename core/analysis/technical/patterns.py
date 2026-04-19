"""
K线形态识别模块
识别常见技术形态：十字星、锤子、吞没、早晨之星等
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math


class PatternType(Enum):
    """形态类型"""
    DOJI = "doji"                          # 十字星
    HAMMER = "hammer"                      # 锤子线
    INVERTED_HAMMER = "inverted_hammer"    # 倒锤子
    ENGULFING_BULLISH = "engulfing_bullish"  # 看涨吞没
    ENGULFING_BEARISH = "engulfing_bearish"  # 看跌吞没
    MORNING_STAR = "morning_star"         # 早晨之星
    EVENING_STAR = "evening_star"         # 黄昏之星
    HAMMER_HANGING = "hanging_man"         # 上吊线
    PIERCING_LINE = "piercing_line"        # 刺透形态
    DARK_CLOUD_COVER = "dark_cloud_cover"  # 乌云盖顶
    THREE_WHITE_SOLDIERS = "three_white_soldiers"  # 三白兵
    THREE_BLACK_CROWS = "three_black_crows"  # 三乌鸦
    MARUBOZU_BULLISH = "marubozu_bullish"  # 光头阳线
    MARUBOZU_BEARISH = "marubozu_bearish"  # 光头阴线
    SPINNING_TOP = "spinning_top"          # 纺锤线
    HIGH_WAVE = "high_wave"                # 高浪线
    DRAGONFLY = "dragonfly"                # 蜻蜓十字
    GRAVESTONE = "gravestone"              # 墓碑十字
    INSIDE_BAR = "inside_bar"              # 内含线
    OUTSIDE_BAR = "outside_bar"            # 外包线
    BREAKAWAY = "breakaway"                # 脱离形态
    TWEEZER_BOTTOM = "tweezer_bottom"      # 双重底
    TWEEZER_TOP = "tweezer_top"            # 双重顶


@dataclass
class Candle:
    """单根K线"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_top(self) -> float:
        return max(self.open, self.close)

    @property
    def body_bottom(self) -> float:
        return min(self.open, self.close)

    @property
    def upper_shadow(self) -> float:
        return self.high - self.body_top

    @property
    def lower_shadow(self) -> float:
        return self.body_bottom - self.low

    @property
    def total_range(self) -> float:
        return self.high - self.low if self.high > self.low else 1e-10

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def is_doji(self) -> bool:
        return self.body / self.total_range < 0.1


@dataclass
class PatternResult:
    """形态识别结果"""
    pattern: PatternType
    direction: str  # "bullish", "bearish", "neutral"
    strength: float  # 0-1, 强度
    candles: List[Candle]
    description: str
    signal: str  # "BUY", "SELL", "NEUTRAL"
    confidence: float  # 0-100

    def to_dict(self) -> Dict:
        return {
            "pattern": self.pattern.value,
            "direction": self.direction,
            "strength": round(self.strength, 2),
            "candles": len(self.candles),
            "description": self.description,
            "signal": self.signal,
            "confidence": round(self.confidence, 1),
        }


def klines_to_candles(klines: List) -> List[Candle]:
    """将原始K线数据转换为Candle对象"""
    candles = []
    for k in klines:
        if isinstance(k, dict):
            c = Candle(
                timestamp=k.get("timestamp", k.get("open_time", 0)),
                open=float(k["open"]),
                high=float(k["high"]),
                low=float(k["low"]),
                close=float(k["close"]),
                volume=float(k.get("volume", k.get("qvolume", 0))),
            )
        elif isinstance(k, (list, tuple)) and len(k) >= 5:
            c = Candle(
                timestamp=int(k[0]),
                open=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
                volume=float(k[5]) if len(k) > 5 else 0,
            )
        else:
            continue
        candles.append(c)
    return candles


class PatternRecognizer:
    """
    K线形态识别器
    识别多种常见技术形态，提供信号和置信度
    """

    def __init__(self):
        self.min_candles = 2  # 最少K线数

    def recognize_all(self, candles: List[Candle]) -> List[PatternResult]:
        """识别所有形态"""
        results = []

        if len(candles) < 2:
            return results

        # 单根K线形态
        for i, candle in enumerate(candles):
            r = self._recognize_single(candle)
            if r:
                results.append(r)

        # 双K线形态
        for i in range(len(candles) - 1):
            r = self._recognize_two_candle(candles[i], candles[i+1])
            if r:
                results.append(r)

        # 三K线形态
        for i in range(len(candles) - 2):
            r = self._recognize_three_candle(
                candles[i], candles[i+1], candles[i+2]
            )
            if r:
                results.append(r)

        # 按强度排序
        results.sort(key=lambda x: x.strength, reverse=True)
        return results

    def _recognize_single(self, c: Candle) -> Optional[PatternResult]:
        """识别单根K线形态"""

        body_ratio = c.body / c.total_range if c.total_range > 0 else 0
        lower_shadow_ratio = c.lower_shadow / c.total_range if c.total_range > 0 else 0
        upper_shadow_ratio = c.upper_shadow / c.total_range if c.total_range > 0 else 0

        # 十字星
        if body_ratio < 0.05 and c.total_range > 0:
            if c.lower_shadow > c.upper_shadow * 2:
                return PatternResult(
                    pattern=PatternType.DRAGONFLY,
                    direction="neutral",
                    strength=0.7,
                    candles=[c],
                    description="蜻蜓十字：下影线极长，预示潜在反转",
                    signal="NEUTRAL",
                    confidence=70,
                )
            elif c.upper_shadow > c.lower_shadow * 2:
                return PatternResult(
                    pattern=PatternType.GRAVESTONE,
                    direction="neutral",
                    strength=0.7,
                    candles=[c],
                    description="墓碑十字：上影线极长，看跌信号",
                    signal="NEUTRAL",
                    confidence=70,
                )
            else:
                return PatternResult(
                    pattern=PatternType.DOJI,
                    direction="neutral",
                    strength=0.6,
                    candles=[c],
                    description="十字星：多空力量均衡，市场犹豫",
                    signal="NEUTRAL",
                    confidence=65,
                )

        # 锤子线（看涨）
        if (lower_shadow_ratio > 0.6 and
            upper_shadow_ratio < 0.1 and
            body_ratio < 0.4 and
            c.is_bearish):  # 开盘>收盘
            strength = 0.7 + lower_shadow_ratio * 0.3
            return PatternResult(
                pattern=PatternType.HAMMER,
                direction="bullish",
                strength=min(strength, 1.0),
                candles=[c],
                description=f"锤子线：下影线{lower_shadow_ratio*100:.0f}%占主导，看涨反转",
                signal="BUY",
                confidence=min(strength * 100, 95),
            )

        # 倒锤子（看涨）
        if (upper_shadow_ratio > 0.6 and
            lower_shadow_ratio < 0.1 and
            body_ratio < 0.4 and
            c.is_bullish):
            strength = 0.7 + upper_shadow_ratio * 0.3
            return PatternResult(
                pattern=PatternType.INVERTED_HAMMER,
                direction="bullish",
                strength=min(strength, 1.0),
                candles=[c],
                description=f"倒锤子：上影线{upper_shadow_ratio*100:.0f}%占主导，潜在看涨",
                signal="BUY",
                confidence=min(strength * 100, 85),
            )

        # 上吊线（看跌）
        if (lower_shadow_ratio > 0.5 and
            upper_shadow_ratio < 0.15 and
            body_ratio < 0.35 and
            c.is_bullish):
            return PatternResult(
                pattern=PatternType.HAMMER_HANGING,
                direction="bearish",
                strength=0.75,
                candles=[c],
                description="上吊线：出现在高位，看跌反转信号",
                signal="SELL",
                confidence=78,
            )

        # 光头阳线（大阳线）
        if (c.is_bullish and
            upper_shadow_ratio < 0.02 and
            body_ratio > 0.85):
            return PatternResult(
                pattern=PatternType.MARUBOZU_BULLISH,
                direction="bullish",
                strength=0.8,
                candles=[c],
                description="光头阳线：买盘强劲，趋势延续",
                signal="BUY",
                confidence=82,
            )

        # 光头阴线（大阴线）
        if (c.is_bearish and
            upper_shadow_ratio < 0.02 and
            body_ratio > 0.85):
            return PatternResult(
                pattern=PatternType.MARUBOZU_BEARISH,
                direction="bearish",
                strength=0.8,
                candles=[c],
                description="光头阴线：卖盘强劲，趋势延续",
                signal="SELL",
                confidence=82,
            )

        # 纺锤线（震荡信号）
        if 0.25 < body_ratio < 0.5 and lower_shadow_ratio > 0.2 and upper_shadow_ratio > 0.2:
            return PatternResult(
                pattern=PatternType.SPINNING_TOP,
                direction="neutral",
                strength=0.5,
                candles=[c],
                description="纺锤线：多空拉锯，市场震荡",
                signal="NEUTRAL",
                confidence=55,
            )

        return None

    def _recognize_two_candle(self, c1: Candle, c2: Candle) -> Optional[PatternResult]:
        """识别双K线形态"""

        # 看涨吞没
        if (c1.is_bearish and c2.is_bullish and
            c2.close > c1.open and c2.open < c1.close and
            c2.body > c1.body):
            body_coverage = c2.body / c1.body if c1.body > 0 else 0
            strength = min(0.75 + body_coverage * 0.15, 1.0)
            return PatternResult(
                pattern=PatternType.ENGULFING_BULLISH,
                direction="bullish",
                strength=strength,
                candles=[c1, c2],
                description="看涨吞没：阳线完全吞没前一根阴线，强力看涨信号",
                signal="BUY",
                confidence=strength * 100,
            )

        # 看跌吞没
        if (c1.is_bullish and c2.is_bearish and
            c2.close < c1.open and c2.open > c1.close and
            c2.body > c1.body):
            body_coverage = c2.body / c1.body if c1.body > 0 else 0
            strength = min(0.75 + body_coverage * 0.15, 1.0)
            return PatternResult(
                pattern=PatternType.ENGULFING_BEARISH,
                direction="bearish",
                strength=strength,
                candles=[c1, c2],
                description="看跌吞没：阴线完全吞没前一根阳线，强力看跌信号",
                signal="SELL",
                confidence=strength * 100,
            )

        # 刺透形态（弱版看涨吞没）
        if (c1.is_bearish and c2.is_bullish and
            c2.close > (c1.open + c1.close) / 2 and
            c2.close <= c1.open):
            return PatternResult(
                pattern=PatternType.PIERCING_LINE,
                direction="bullish",
                strength=0.65,
                candles=[c1, c2],
                description="刺透形态：阳线刺入阴线50%以上，中度看涨",
                signal="BUY",
                confidence=68,
            )

        # 乌云盖顶
        if (c1.is_bullish and c2.is_bearish and
            c2.close < (c1.open + c1.close) / 2 and
            c2.close >= c1.open):
            return PatternResult(
                pattern=PatternType.DARK_CLOUD_COVER,
                direction="bearish",
                strength=0.65,
                candles=[c1, c2],
                description="乌云盖顶：阴线插入阳线50%以上，中度看跌",
                signal="SELL",
                confidence=68,
            )

        # 内含线（inside bar）
        if (c2.high < c1.high and c2.low > c1.low and
            c2.body < c1.body):
            return PatternResult(
                pattern=PatternType.INSIDE_BAR,
                direction="neutral",
                strength=0.55,
                candles=[c1, c2],
                description="内含线：价格压缩，突破在即",
                signal="NEUTRAL",
                confidence=60,
            )

        # 外包线（outside bar）
        if (c2.high > c1.high and c2.low < c1.low and
            c2.body > c1.body):
            strength = 0.7
            direction = "bullish" if c2.is_bullish else "bearish"
            signal = "BUY" if c2.is_bullish else "SELL"
            return PatternResult(
                pattern=PatternType.OUTSIDE_BAR,
                direction=direction,
                strength=strength,
                candles=[c1, c2],
                description="外包线：波动扩大，趋势确立",
                signal=signal,
                confidence=75,
            )

        # 双重底
        if (abs(c1.low - c2.low) / max(c1.low, c2.low, 1) < 0.01 and
            c1.low < c1.high * 0.98 and
            abs(c1.close - c2.close) / max(c1.close, c2.close, 1) > 0.01):
            return PatternResult(
                pattern=PatternType.TWEEZER_BOTTOM,
                direction="bullish",
                strength=0.7,
                candles=[c1, c2],
                description="双重底：两次触及相近低点，获得支撑",
                signal="BUY",
                confidence=75,
            )

        # 双重顶
        if (abs(c1.high - c2.high) / max(c1.high, c2.high, 1) < 0.01 and
            c1.high > c1.low * 1.02 and
            abs(c1.close - c2.close) / max(c1.close, c2.close, 1) > 0.01):
            return PatternResult(
                pattern=PatternType.TWEEZER_TOP,
                direction="bearish",
                strength=0.7,
                candles=[c1, c2],
                description="双重顶：两次触及相近高点，遭遇阻力",
                signal="SELL",
                confidence=75,
            )

        return None

    def _recognize_three_candle(
        self, c1: Candle, c2: Candle, c3: Candle
    ) -> Optional[PatternResult]:
        """识别三K线形态"""

        # 早晨之星
        if (c1.is_bearish and c1.body / c1.total_range > 0.5 and
            c2.body / c2.total_range < 0.3 and  # 小实体
            c3.is_bullish and c3.body / c3.total_range > 0.5 and
            c3.close > (c1.open + c1.close) / 2):  # 收复一半以上
            avg_body = (c1.body + c2.body + c3.body) / 3
            strength = min(0.75 + c3.body / avg_body * 0.15, 1.0)
            return PatternResult(
                pattern=PatternType.MORNING_STAR,
                direction="bullish",
                strength=strength,
                candles=[c1, c2, c3],
                description="早晨之星：三K线底部反转形态，强烈看涨信号",
                signal="BUY",
                confidence=strength * 100,
            )

        # 黄昏之星
        if (c1.is_bullish and c1.body / c1.total_range > 0.5 and
            c2.body / c2.total_range < 0.3 and
            c3.is_bearish and c3.body / c3.total_range > 0.5 and
            c3.close < (c1.open + c1.close) / 2):
            avg_body = (c1.body + c2.body + c3.body) / 3
            strength = min(0.75 + c3.body / avg_body * 0.15, 1.0)
            return PatternResult(
                pattern=PatternType.EVENING_STAR,
                direction="bearish",
                strength=strength,
                candles=[c1, c2, c3],
                description="黄昏之星：三K线顶部反转形态，强烈看跌信号",
                signal="SELL",
                confidence=strength * 100,
            )

        # 三白兵
        if (c1.is_bullish and c2.is_bullish and c3.is_bullish and
            c1.body / c1.total_range > 0.6 and
            c2.body / c2.total_range > 0.6 and
            c3.body / c3.total_range > 0.6 and
            c2.close > c1.close and c3.close > c2.close and
            c1.open > c2.low and c2.open > c3.low):  # 阶梯上升
            return PatternResult(
                pattern=PatternType.THREE_WHITE_SOLDIERS,
                direction="bullish",
                strength=0.88,
                candles=[c1, c2, c3],
                description="三白兵：三根连续大阳线，阶梯上升，极强看涨",
                signal="BUY",
                confidence=90,
            )

        # 三乌鸦
        if (c1.is_bearish and c2.is_bearish and c3.is_bearish and
            c1.body / c1.total_range > 0.6 and
            c2.body / c2.total_range > 0.6 and
            c3.body / c3.total_range > 0.6 and
            c2.close < c1.close and c3.close < c2.close and
            c1.open < c2.high and c2.open < c3.high):
            return PatternResult(
                pattern=PatternType.THREE_BLACK_CROWS,
                direction="bearish",
                strength=0.88,
                candles=[c1, c2, c3],
                description="三乌鸦：三根连续大阴线，阶梯下降，极强看跌",
                signal="SELL",
                confidence=90,
            )

        return None

    def get_overall_signal(self, patterns: List[PatternResult]) -> Tuple[str, float]:
        """从多个形态中综合得出信号"""
        if not patterns:
            return "NEUTRAL", 0.0

        buy_count = sum(1 for p in patterns if p.signal == "BUY")
        sell_count = sum(1 for p in patterns if p.signal == "SELL")
        buy_strength = sum(p.strength for p in patterns if p.signal == "BUY")
        sell_strength = sum(p.strength for p in patterns if p.signal == "SELL")

        total = buy_count + sell_count
        if total == 0:
            return "NEUTRAL", 0.0

        buy_avg = buy_strength / buy_count if buy_count > 0 else 0
        sell_avg = sell_strength / sell_count if sell_count > 0 else 0

        if buy_count > sell_count * 1.5 and buy_avg > 0.65:
            return "STRONG_BUY", buy_avg
        elif buy_count > sell_count:
            return "BUY", (buy_avg + sell_avg) / 2
        elif sell_count > buy_count * 1.5 and sell_avg > 0.65:
            return "STRONG_SELL", sell_avg
        elif sell_count > buy_count:
            return "SELL", (buy_avg + sell_avg) / 2
        else:
            return "NEUTRAL", 0.5


def recognize_patterns(klines: List, limit: int = 100) -> Dict:
    """
    便捷函数：识别K线形态
    klines: 原始K线数据（list of dict or list of list）
    limit: 分析最近N根K线
    """
    candles = klines_to_candles(klines[-limit:])
    recognizer = PatternRecognizer()
    patterns = recognizer.recognize_all(candles)
    signal, score = recognizer.get_overall_signal(patterns)

    return {
        "signal": signal,
        "score": round(score, 2),
        "patterns_found": len(patterns),
        "strongest_pattern": patterns[0].to_dict() if patterns else None,
        "all_patterns": [p.to_dict() for p in patterns[:10]],
        "bullish_count": sum(1 for p in patterns if p.direction == "bullish"),
        "bearish_count": sum(1 for p in patterns if p.direction == "bearish"),
        "candles_analyzed": len(candles),
    }
