"""
支撑阻力位计算模块
识别关键价格位：支撑位、阻力位、斐波那契回撤、趋势线、Pivot点
"""
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum


class LevelType(Enum):
    SUPPORT = "support"
    RESISTANCE = "resistance"
    PIVOT_R = "pivot_r"
    PIVOT_S = "pivot_s"
    FIB_382 = "fib_382"
    FIB_500 = "fib_500"
    FIB_618 = "fib_618"
    FIB_786 = "fib_786"
    FIB_1272 = "fib_1272"
    FIB_1618 = "fib_1618"
    SWING_HIGH = "swing_high"
    SWING_LOW = "swing_low"
    EMA_LEVEL = "ema_level"
    ROUND_LEVEL = "round_level"


@dataclass
class PriceLevel:
    """价格位"""
    price: float
    level_type: LevelType
    strength: float  # 0-1 强度
    touches: int     # 价格触及次数
    recency: float   # 最近触及的时间权重
    description: str = ""
    label: str = ""

    def calc_score(self) -> float:
        """综合评分 = 强度 × 触及次数 × 时间权重"""
        return self.strength * min(self.touches, 5) * self.recency

    def to_dict(self) -> Dict:
        return {
            "price": round(self.price, 4),
            "type": self.level_type.value,
            "strength": round(self.strength, 2),
            "touches": self.touches,
            "score": round(self.calc_score(), 3),
            "description": self.description,
            "label": self.label,
        }


class SupportResistanceAnalyzer:
    """
    支撑阻力位分析器
    多种方法识别关键价格位
    """

    def __init__(self, price_data: List[Dict]):
        """
        price_data: K线数据列表，每项包含 high, low, close, open
        """
        self.prices = price_data
        self.highs = [float(p["high"]) for p in price_data]
        self.lows = [float(p["low"]) for p in price_data]
        self.closes = [float(p["close"]) for p in price_data]
        self.opens = [float(p["open"]) for p in price_data]
        self.length = len(price_data)

    def find_all_levels(self, lookback: int = 100) -> List[PriceLevel]:
        """
        综合多种方法找出所有关键位
        lookback: 分析最近N根K线
        """
        data = min(lookback, self.length)
        highs = self.highs[-data:]
        lows = self.lows[-data:]
        closes = self.closes[-data:]

        levels = []

        # 1. 摆动高低点
        levels.extend(self._swing_points(highs, lows))

        # 2. 斐波那契回撤
        levels.extend(self._fibonacci_levels(highs, lows))

        # 3. Pivot点
        levels.extend(self._pivot_points())

        # 4. 成交量加权价格位
        levels.extend(self._volume_weighted_levels())

        # 5. 均线密集区
        levels.extend(self._ema_clusters())

        # 6. 整数关口
        levels.extend(self._round_levels())

        # 7. 合并相近水平
        levels = self._merge_nearby_levels(levels)

        # 8. 计算触及次数
        levels = self._count_touches(levels)

        # 9. 计算时间权重（近期更可靠）
        levels = self._apply_recency(levels)

        # 按评分排序
        levels.sort(key=lambda x: x.calc_score(), reverse=True)
        return levels

    def _swing_points(self, highs: List[float], lows: List[float]) -> List[PriceLevel]:
        """识别摆动高点/低点"""
        levels = []
        if len(highs) < 5:
            return levels

        # 局部高点
        for i in range(2, len(highs) - 2):
            if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and
                highs[i] > highs[i+1] and highs[i] > highs[i+2]):
                # 计算回撤深度
                left_drop = highs[i] - min(highs[max(0,i-10):i])
                right_drop = highs[i] - min(highs[i+1:min(len(highs),i+11)])
                avg_drop = (left_drop + right_drop) / 2
                strength = min(avg_drop / highs[i] * 10, 1.0)

                levels.append(PriceLevel(
                    price=highs[i],
                    level_type=LevelType.SWING_HIGH,
                    strength=strength,
                    touches=1,
                    recency=0.5,
                    description=f"摆动高点，回撤深度{avg_drop/highs[i]*100:.1f}%",
                    label=f"SW{highs[i]:.0f}",
                ))

        # 局部低点
        for i in range(2, len(lows) - 2):
            if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and
                lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                left_rise = max(lows[max(0,i-10):i]) - lows[i]
                right_rise = max(lows[i+1:min(len(lows),i+11)]) - lows[i]
                avg_rise = (left_rise + right_rise) / 2
                strength = min(avg_rise / lows[i] * 10, 1.0)

                levels.append(PriceLevel(
                    price=lows[i],
                    level_type=LevelType.SWING_LOW,
                    strength=strength,
                    touches=1,
                    recency=0.5,
                    description=f"摆动低点，反弹高度{avg_rise/lows[i]*100:.1f}%",
                    label=f"SL{lows[i]:.0f}",
                ))

        return levels

    def _fibonacci_levels(self, highs: List[float], lows: List[float]) -> List[PriceLevel]:
        """斐波那契回撤/扩展位"""
        levels = []
        recent_high = max(highs)
        recent_low = min(lows)
        diff = recent_high - recent_low

        if diff < recent_low * 0.01:  # 波动太小
            return levels

        fib_ratios = [
            (0.382, LevelType.FIB_382),
            (0.500, LevelType.FIB_500),
            (0.618, LevelType.FIB_618),
            (0.786, LevelType.FIB_786),
            (1.272, LevelType.FIB_1272),
            (1.618, LevelType.FIB_1618),
        ]

        for ratio, level_type in fib_ratios:
            if ratio < 1:
                # 回撤位
                price = recent_high - diff * ratio
                desc = f"斐波那契 {ratio*100:.1f}% 回撤位"
            else:
                # 扩展位
                price = recent_low + diff * ratio
                desc = f"斐波那契 {ratio*100:.1f}% 扩展位"

            levels.append(PriceLevel(
                price=price,
                level_type=level_type,
                strength=0.7 if ratio in (0.382, 0.618) else 0.6,
                touches=1,
                recency=0.6,
                description=desc,
            ))

        return levels

    def _pivot_points(self) -> List[PriceLevel]:
        """经典Pivot点计算"""
        levels = []
        if self.length < 2:
            return levels

        last_high = self.highs[-2]
        last_low = self.lows[-2]
        last_close = self.closes[-2]

        # 枢轴点
        pivot = (last_high + last_low + last_close) / 3

        # 支撑位
        s1 = 2 * pivot - last_high
        s2 = pivot - (last_high - last_low)
        s3 = last_low - 2 * (last_high - pivot)

        # 阻力位
        r1 = 2 * pivot - last_low
        r2 = pivot + (last_high - last_low)
        r3 = last_high + 2 * (pivot - last_low)

        current = self.closes[-1]

        for price, ltype, desc in [
            (s1, LevelType.PIVOT_S, "Pivot S1 支撑"),
            (s2, LevelType.PIVOT_S, "Pivot S2 支撑"),
            (r1, LevelType.PIVOT_R, "Pivot R1 阻力"),
            (r2, LevelType.PIVOT_R, "Pivot R2 阻力"),
        ]:
            # 离当前价格越近越重要
            distance = abs(price - current) / current
            strength = max(0.5, 1.0 - distance * 10)
            levels.append(PriceLevel(
                price=price,
                level_type=ltype,
                strength=strength,
                touches=1,
                recency=0.7,
                description=desc,
            ))

        return levels

    def _volume_weighted_levels(self) -> List[PriceLevel]:
        """成交量加权价格位 (VWAP)"""
        levels = []
        if not hasattr(self, 'volumes') or not self.volumes:
            return levels

        total_vol = sum(self.volumes)
        if total_vol == 0:
            return levels

        vwap = sum(p * v for p, v in zip(self.closes, self.volumes)) / total_vol
        current = self.closes[-1]

        levels.append(PriceLevel(
            price=vwap,
            level_type=LevelType.SUPPORT if vwap < current else LevelType.RESISTANCE,
            strength=0.75,
            touches=3,
            recency=0.6,
            description=f"成交量加权均价 (VWAP): ${vwap:.2f}",
        ))
        return levels

    def _ema_clusters(self) -> List[PriceLevel]:
        """均线密集区"""
        levels = []
        if self.length < 50:
            return levels

        # 计算常用均线
        ema_periods = [9, 20, 50, 100, 200]
        emas = {}
        for period in ema_periods:
            if self.length >= period:
                emas[period] = self._calc_ema(self.closes, period)

        # 找均线聚集区
        ema_values = [v for v in emas.values() if v is not None]
        if len(ema_values) < 2:
            return levels

        # 检查是否有均线靠近
        for i in range(len(ema_values)):
            for j in range(i+1, len(ema_values)):
                v1, v2 = ema_values[i], ema_values[j]
                if v1 == 0:
                    continue
                proximity = abs(v1 - v2) / max(v1, v2)
                if proximity < 0.005:  # 0.5%以内
                    avg_price = (v1 + v2) / 2
                    levels.append(PriceLevel(
                        price=avg_price,
                        level_type=LevelType.EMA_LEVEL,
                        strength=0.65,
                        touches=2,
                        recency=0.5,
                        description="均线密集区",
                    ))

        return levels

    def _calc_ema(self, data: List[float], period: int) -> Optional[float]:
        """计算EMA"""
        if len(data) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _round_levels(self) -> List[PriceLevel]:
        """整数关口位"""
        levels = []
        current = self.closes[-1]

        # 找出最近的整数关口
        base = 10 ** (len(str(int(current))) - 1)
        nearby_ints = [
            int(current // base) * base,
            int(current // base) * base + base,
            int(current // base) * base - base,
        ]

        for int_price in nearby_ints:
            if int_price > 0 and abs(int_price - current) / current < 0.05:
                levels.append(PriceLevel(
                    price=float(int_price),
                    level_type=LevelType.ROUND_LEVEL,
                    strength=0.6,
                    touches=1,
                    recency=0.5,
                    description=f"整数关口 ${int_price:,.0f}",
                ))

        return levels

    def _merge_nearby_levels(
        self, levels: List[PriceLevel], threshold: float = 0.005
    ) -> List[PriceLevel]:
        """合并相近的价格位"""
        if not levels:
            return []

        # 按价格排序
        sorted_levels = sorted(levels, key=lambda x: x.price)

        merged = []
        current_group = [sorted_levels[0]]

        for level in sorted_levels[1:]:
            prev = current_group[-1]
            if prev.price == 0:
                continue
            distance = abs(level.price - prev.price) / prev.price

            if distance < threshold:  # 0.5%以内视为同一水平
                current_group.append(level)
            else:
                # 完成当前组
                merged.append(self._merge_group(current_group))
                current_group = [level]

        # 最后一组
        if current_group:
            merged.append(self._merge_group(current_group))

        return merged

    def _merge_group(self, group: List[PriceLevel]) -> PriceLevel:
        """合并一组相近的价格位"""
        avg_price = sum(l.price for l in group) / len(group)
        max_strength = max(l.strength for l in group)
        total_touches = sum(l.touches for l in group)
        max_recency = max(l.recency for l in group)
        primary = max(group, key=lambda x: x.strength)

        return PriceLevel(
            price=avg_price,
            level_type=primary.level_type,
            strength=max_strength,
            touches=min(total_touches, 5),
            recency=max_recency,
            description=f"合并{len(group)}个相近水平",
            label=primary.label or primary.level_type.value,
        )

    def _count_touches(self, levels: List[PriceLevel]) -> List[PriceLevel]:
        """计算每个水平被触及的次数"""
        for level in levels:
            touches = 0
            for i in range(len(self.highs)):
                high, low = self.highs[i], self.lows[i]
                if low <= level.price <= high:
                    touches += 1
            level.touches = min(touches, 5)
        return levels

    def _apply_recency(self, levels: List[PriceLevel]) -> List[PriceLevel]:
        """应用时间权重：最近触及的位更可靠"""
        for level in levels:
            # 在最近20%数据中触及过
            recent = self.length // 5
            recent_touched = False
            for i in range(self.length - recent, self.length):
                if self.lows[i] <= level.price <= self.highs[i]:
                    recent_touched = True
                    break
            level.recency = 1.0 if recent_touched else 0.5
        return levels

    def get_key_levels(
        self, num_levels: int = 8
    ) -> Dict:
        """
        获取最重要的支撑阻力位
        返回支撑位列表、阻力位列表和分析摘要
        """
        all_levels = self.find_all_levels()

        supports = [l for l in all_levels if l.level_type in (
            LevelType.SUPPORT, LevelType.PIVOT_S, LevelType.SWING_LOW, LevelType.FIB_382
        )]
        resistances = [l for l in all_levels if l.level_type in (
            LevelType.RESISTANCE, LevelType.PIVOT_R, LevelType.SWING_HIGH, LevelType.FIB_786
        )]

        current = self.closes[-1] if self.closes else 0

        # 离价格最近的位
        nearest_support = None
        nearest_resistance = None
        for s in supports:
            if s.price < current:
                if nearest_support is None or s.price > nearest_support.price:
                    nearest_support = s

        for r in resistances:
            if r.price > current:
                if nearest_resistance is None or r.price < nearest_resistance.price:
                    nearest_resistance = r

        # 支撑/阻力距离
        support_distance = 0.0
        if nearest_support and current > 0:
            support_distance = (current - nearest_support.price) / current * 100

        resistance_distance = 0.0
        if nearest_resistance and current > 0:
            resistance_distance = (nearest_resistance.price - current) / current * 100

        return {
            "current_price": round(current, 4),
            "nearest_support": nearest_support.to_dict() if nearest_support else None,
            "nearest_resistance": nearest_resistance.to_dict() if nearest_resistance else None,
            "support_distance_pct": round(support_distance, 2),
            "resistance_distance_pct": round(resistance_distance, 2),
            "all_supports": [l.to_dict() for l in supports[:num_levels]],
            "all_resistances": [l.to_dict() for l in resistances[:num_levels]],
            "total_levels": len(all_levels),
        }


def analyze_support_resistance(klines: List, lookback: int = 100) -> Dict:
    """
    便捷函数：分析支撑阻力位
    """
    if not klines or len(klines) < 5:
        return {"error": "数据不足"}

    # 补充成交量（如果K线数据没有）
    for k in klines:
        if "volume" not in k and len(k) > 5:
            k["volume"] = float(k[5]) if len(k) > 5 else 0

    analyzer = SupportResistanceAnalyzer(klines)
    result = analyzer.get_key_levels()

    # 添加形态分析
    from core.analysis.technical.patterns import recognize_patterns
    pattern_result = recognize_patterns(klines, limit=20)
    result["pattern_summary"] = pattern_result

    return result
