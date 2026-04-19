"""
技术分析指标计算引擎
支持：RSI / MACD / Bollinger Bands / EMA / KDJ / ATR / 趋势判断
"""
import math
from typing import Optional
from dataclasses import dataclass
from core.utils.logger import logger
from core.utils.helpers import safe_execute


# ─────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────
@dataclass
class Kline:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TechnicalResult:
    """技术分析结果"""
    # 趋势指标
    trend: str           # UP / DOWN / SIDEWAYS
    trend_strength: float  # 0-1

    # 动量指标
    rsi: Optional[float]      # 0-100
    rsi_signal: str           # OVERBOUGHT / NEUTRAL / OVERSOLD

    macd: Optional[float]     # MACD线
    macd_signal: Optional[float]  # Signal线
    macd_histogram: Optional[float]  # 柱状图
    macd_signal_text: str     # 金叉/死叉/中性

    # 布林带
    bb_upper: Optional[float]
    bb_middle: Optional[float]
    bb_lower: Optional[float]
    bb_width: Optional[float]  # 带宽 %
    bb_position: Optional[float]  # 价格在带中位置 %

    # 均线
    ema_9: Optional[float]
    ema_20: Optional[float]
    ema_50: Optional[float]
    ema_200: Optional[float]

    # ATR
    atr_14: Optional[float]

    # 综合评分
    bullish_signals: int
    bearish_signals: int
    overall_score: float    # -100 到 +100


# ─────────────────────────────────────────────────────────────
# 核心计算函数
# ─────────────────────────────────────────────────────────────
def calc_sma(prices: list[float], period: int) -> list[float]:
    """简单移动平均"""
    if len(prices) < period:
        return []
    sma = []
    for i in range(period - 1, len(prices)):
        sma.append(sum(prices[i - period + 1:i + 1]) / period)
    return sma


def calc_ema(prices: list[float], period: int) -> list[float]:
    """指数移动平均"""
    if len(prices) < period:
        return []
    multiplier = 2 / (period + 1)
    ema = [sum(prices[:period]) / period]
    for price in prices[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema


def calc_rsi(prices: list[float], period: int = 14) -> list[float]:
    """相对强弱指数 RSI"""
    if len(prices) < period + 1:
        return []
    
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(c, 0) for c in changes]
    losses = [abs(min(c, 0)) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsi_values = []
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - 100 / (1 + rs))

    return rsi_values


def calc_macd(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[list, list, list]:
    """
    MACD 计算
    返回: (macd_line, signal_line, histogram)
    """
    if len(prices) < slow + signal:
        return [], [], []

    ema_fast = calc_ema(prices, fast)
    ema_slow = calc_ema(prices, slow)

    # 对齐
    offset = slow - fast
    macd_line = [ema_fast[i + offset] - ema_slow[i] for i in range(len(ema_slow))]
    signal_line = calc_ema(macd_line, signal)

    # 对齐signal
    signal_offset = signal - 1
    histogram = []
    if len(signal_line) > 0:
        for i in range(signal_offset, len(macd_line)):
            idx = i - signal_offset
            if idx < len(signal_line):
                histogram.append(macd_line[i] - signal_line[idx])

    return macd_line, signal_line, histogram


def calc_bollinger(prices: list[float], period: int = 20, std_dev: float = 2.0) -> tuple[list, list, list]:
    """布林带"""
    if len(prices) < period:
        return [], [], []

    sma_values = calc_sma(prices, period)
    upper = []
    lower = []

    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1:i + 1]
        mean = sum(window) / period
        variance = sum((p - mean) ** 2 for p in window) / period
        std = math.sqrt(variance)
        upper.append(mean + std_dev * std)
        lower.append(mean - std_dev * std)

    return upper, sma_values, lower


def calc_atr(klines: list[Kline], period: int = 14) -> list[float]:
    """Average True Range"""
    if len(klines) < period + 1:
        return []

    trs = []
    for i in range(1, len(klines)):
        high = klines[i].high
        low = klines[i].low
        prev_close = klines[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    if len(trs) < period:
        return []

    atr = [sum(trs[:period]) / period]
    for tr in trs[period:]:
        atr.append((atr[-1] * (period - 1) + tr) / period)

    return atr


def detect_trend(prices: list[float], ema_9: float, ema_20: float, ema_50: float) -> tuple[str, float]:
    """
    趋势判断
    返回: (趋势方向, 强度0-1)
    """
    if len(prices) < 2:
        return "SIDEWAYS", 0.0

    # 价格位置判断
    current = prices[-1]
    recent_high = max(prices[-20:]) if len(prices) >= 20 else max(prices)
    recent_low = min(prices[-20:]) if len(prices) >= 20 else min(prices)
    mid_range = (recent_high + recent_low) / 2

    # 均线多头/空头排列
    bullish_count = 0
    if ema_9 and ema_9 > ema_20:
        bullish_count += 1
    if ema_20 and ema_20 > ema_50:
        bullish_count += 1
    if current > ema_9 if ema_9 else False:
        bullish_count += 1

    # 价格动量
    if len(prices) >= 5:
        momentum = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] != 0 else 0
    else:
        momentum = 0

    strength = min(abs(bullish_count / 3) + abs(momentum) * 10, 1.0)

    if bullish_count >= 2 and current > mid_range:
        return "UP", strength
    elif bullish_count <= 1 and current < mid_range:
        return "DOWN", strength
    else:
        return "SIDEWAYS", strength * 0.5


# ─────────────────────────────────────────────────────────────
# 综合分析
# ─────────────────────────────────────────────────────────────
@safe_execute(default=None)
def analyze(klines: list[dict], symbol: str = "BTC") -> TechnicalResult:
    """
    对K线数据进行完整技术分析
    klines: 从API获取的原始K线列表
    """
    if not klines or len(klines) < 30:
        logger.warning(f"K线数据不足: {len(klines) if klines else 0}条 (需要≥30)")
        return _empty_result()

    # 转换为 Kline 对象
    bars = []
    for k in klines:
        try:
            bar = Kline(
                timestamp=int(k.get("timestamp") or k.get("open_time", 0)),
                open=float(k.get("open", 0)),
                high=float(k.get("high", 0)),
                low=float(k.get("low", 0)),
                close=float(k.get("close", 0)),
                volume=float(k.get("volume", 0)),
            )
            bars.append(bar)
        except (ValueError, TypeError):
            continue

    if len(bars) < 30:
        return _empty_result()

    closes = [b.close for b in bars]
    current_price = closes[-1]

    # ── 计算各指标 ──
    rsi_values = calc_rsi(closes, 14)
    rsi = round(rsi_values[-1], 2) if rsi_values else None

    macd_line, signal_line, histogram = calc_macd(closes)
    macd = round(macd_line[-1], 4) if macd_line else None
    macd_sig = round(signal_line[-1], 4) if signal_line else None
    macd_hist = round(histogram[-1], 4) if histogram else None

    bb_upper, bb_middle, bb_lower = calc_bollinger(closes, 20, 2.0)
    bb_u = round(bb_upper[-1], 2) if bb_upper else None
    bb_m = round(bb_middle[-1], 2) if bb_middle else None
    bb_l = round(bb_lower[-1], 2) if bb_lower else None

    # 布林带宽度
    if bb_u and bb_l and bb_m:
        bb_width = round((bb_u - bb_l) / bb_m * 100, 2)
        bb_position = round((current_price - bb_l) / (bb_u - bb_l) * 100, 1) if bb_u != bb_l else 50.0
    else:
        bb_width = None
        bb_position = None

    # EMA
    ema_9_list = calc_ema(closes, 9)
    ema_20_list = calc_ema(closes, 20)
    ema_50_list = calc_ema(closes, 50)
    ema_200_list = calc_ema(closes, 200)

    ema_9 = round(ema_9_list[-1], 2) if ema_9_list else None
    ema_20 = round(ema_20_list[-1], 2) if ema_20_list else None
    ema_50 = round(ema_50_list[-1], 2) if ema_50_list else None
    ema_200 = round(ema_200_list[-1], 2) if ema_200_list else None

    # ATR
    atr_values = calc_atr(bars, 14)
    atr_14 = round(atr_values[-1], 4) if atr_values else None

    # ── 信号计数 ──
    bullish = 0
    bearish = 0

    # RSI
    if rsi:
        if rsi > 70:
            bearish += 2
        elif rsi < 30:
            bullish += 2
        elif rsi > 55:
            bullish += 1
        elif rsi < 45:
            bearish += 1

    # MACD
    if macd and macd_sig and histogram:
        if macd > macd_sig and macd_hist > 0:
            bullish += 2
        elif macd < macd_sig and macd_hist < 0:
            bearish += 2

    # 布林带
    if bb_position is not None:
        if bb_position < 20:
            bullish += 1  # 接近下轨，可能反弹
        elif bb_position > 80:
            bearish += 1  # 接近上轨，可能回调
        elif bb_position < 50:
            bullish += 0.5
        else:
            bearish += 0.5

    # 均线
    if ema_9 and ema_9 > ema_20:
        bullish += 1
    elif ema_9 and ema_9 < ema_20:
        bearish += 1

    if ema_50 and current_price > ema_50:
        bullish += 1
    elif ema_50 and current_price < ema_50:
        bearish += 1

    # 趋势
    trend, trend_strength = detect_trend(closes, ema_9, ema_20, ema_50)

    # 综合评分
    max_signals = 10.0
    score = round((bullish - bearish) / max_signals * 100, 1)
    score = max(-100, min(100, score))

    # MACD信号文本
    if macd and macd_sig:
        if macd > macd_sig:
            macd_text = "金叉 (看多)"
        elif macd < macd_sig:
            macd_text = "死叉 (看空)"
        else:
            macd_text = "中性"
    else:
        macd_text = "数据不足"

    # RSI信号
    if rsi:
        if rsi > 70:
            rsi_signal = "OVERBOUGHT"
        elif rsi < 30:
            rsi_signal = "OVERSOLD"
        else:
            rsi_signal = "NEUTRAL"
    else:
        rsi_signal = "N/A"

    return TechnicalResult(
        trend=trend,
        trend_strength=round(trend_strength, 2),
        rsi=rsi,
        rsi_signal=rsi_signal,
        macd=macd,
        macd_signal=macd_sig,
        macd_histogram=macd_hist,
        macd_signal_text=macd_text,
        bb_upper=bb_u,
        bb_middle=bb_m,
        bb_lower=bb_l,
        bb_width=bb_width,
        bb_position=bb_position,
        ema_9=ema_9,
        ema_20=ema_20,
        ema_50=ema_50,
        ema_200=ema_200,
        atr_14=atr_14,
        bullish_signals=bullish,
        bearish_signals=bearish,
        overall_score=score,
    )


def _empty_result() -> TechnicalResult:
    return TechnicalResult(
        trend="SIDEWAYS", trend_strength=0.0,
        rsi=None, rsi_signal="N/A",
        macd=None, macd_signal=None, macd_histogram=None, macd_signal_text="数据不足",
        bb_upper=None, bb_middle=None, bb_lower=None, bb_width=None, bb_position=None,
        ema_9=None, ema_20=None, ema_50=None, ema_200=None,
        atr_14=None, bullish_signals=0, bearish_signals=0, overall_score=0.0,
    )


def technical_to_dict(result: TechnicalResult) -> dict:
    """将技术分析结果转为字典"""
    return {
        "trend": result.trend,
        "trend_strength": result.trend_strength,
        "rsi": result.rsi,
        "rsi_signal": result.rsi_signal,
        "macd": result.macd,
        "macd_signal": result.macd_signal,
        "macd_histogram": result.macd_histogram,
        "macd_signal_text": result.macd_signal_text,
        "bollinger": {
            "upper": result.bb_upper,
            "middle": result.bb_middle,
            "lower": result.bb_lower,
            "width_pct": result.bb_width,
            "price_position_pct": result.bb_position,
        },
        "ema": {
            "ema_9": result.ema_9,
            "ema_20": result.ema_20,
            "ema_50": result.ema_50,
            "ema_200": result.ema_200,
        },
        "atr_14": result.atr_14,
        "bullish_signals": result.bullish_signals,
        "bearish_signals": result.bearish_signals,
        "overall_score": result.overall_score,
    }
