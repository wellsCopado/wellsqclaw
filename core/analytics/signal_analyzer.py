"""
信号分析引擎 - 基于真实数据的综合分析
分析维度: 资金费率 + 持仓量 + 爆仓 + 多空比 + 价格动量
"""
import asyncio
import time
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from enum import Enum
from core.utils.logger import logger
from core.utils.helpers import safe_execute


class Signal(Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    UNKNOWN = "UNKNOWN"


class SignalLevel(Enum):
    """信号强度级别"""
    EXTREME_BULL = "极度看多"
    BULL = "看多"
    NEUTRAL = "中性"
    BEAR = "看空"
    EXTREME_BEAR = "极度看空"


@dataclass
class FactorScore:
    """单个因子评分"""
    name: str
    score: float          # -100 到 +100
    weight: float          # 权重 0-1
    label: str             # 中文描述
    detail: str            # 详细说明
    raw_value: any         # 原始值


@dataclass
class AnalysisResult:
    """完整分析结果"""
    symbol: str
    signal: Signal
    signal_label: str
    confidence: float      # 0-100
    overall_score: float   # -100 到 +100
    factors: List[FactorScore]
    summary: str           # 一句话总结
    risk_level: str        # 低/中/高/极高
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "signal": self.signal.value,
            "signal_label": self.signal_label,
            "confidence": self.confidence,
            "overall_score": self.overall_score,
            "factors": [
                {"name": f.name, "score": f.score, "weight": f.weight, 
                 "label": f.label, "detail": f.detail}
                for f in self.factors
            ],
            "summary": self.summary,
            "risk_level": self.risk_level,
            "timestamp": self.timestamp,
        }


class SignalAnalyzer:
    """
    多因子信号分析引擎
    权重配置:
    - 资金费率: 25% (极端值权重翻倍)
    - 持仓量变化: 20%
    - 多空比: 25% (极端值权重翻倍)
    - 爆仓结构: 15%
    - 价格动量: 15%
    """
    
    # 历史基准 (用于判断极端值)
    FR_THRESHOLD_BULL = 0.05    # 年化 > 60% → 极度看多
    FR_THRESHOLD_BEAR = -0.05   # 年化 < -60% → 极度看空
    FR_THRESHOLD_WARNING = 0.01  # 年化 > 36% → 警告
    
    LS_THRESHOLD_BULL = 1.5     # 多空比 > 1.5 → 多头极端
    LS_THRESHOLD_BEAR = 0.5     # 多空比 < 0.5 → 空头极端
    
    OI_CHANGE_THRESHOLD = 0.15  # 持仓量日变化 > 15%
    
    # 爆仓极端值
    LIQ_EXTREME_THRESHOLD = 150e6  # $150M
    
    def __init__(self):
        self.name = "SignalAnalyzer"
    
    @safe_execute(default=None)
    def analyze(self, market_data: dict) -> AnalysisResult:
        """
        主分析入口
        market_data 需要包含:
        - symbol: str
        - btc_price: float
        - btc_change_pct: float (1h或4h变化)
        - funding_rate: float
        - annual_rate: float
        - open_interest_usd: float
        - open_interest_prev: float (24h前)
        - liq_total_24h: float
        - liq_long_24h: float
        - liq_short_24h: float
        - long_pct: float
        - short_pct: float
        - ls_ratio: float
        """
        symbol = market_data.get('symbol', 'BTC')
        factors = []
        
        # === Factor 1: 资金费率分析 ===
        fr_score, fr_label, fr_detail, fr_raw = self._analyze_funding_rate(
            market_data.get('funding_rate', 0),
            market_data.get('annual_rate', 0),
        )
        factors.append(FactorScore(
            name="资金费率",
            score=fr_score,
            weight=0.25,
            label=fr_label,
            detail=fr_detail,
            raw_value=fr_raw,
        ))
        
        # === Factor 2: 持仓量分析 ===
        oi_score, oi_label, oi_detail, oi_raw = self._analyze_open_interest(
            market_data.get('open_interest_usd', 0),
            market_data.get('open_interest_prev', market_data.get('open_interest_usd', 0)),
            market_data.get('btc_change_pct', 0),
        )
        factors.append(FactorScore(
            name="持仓量",
            score=oi_score,
            weight=0.20,
            label=oi_label,
            detail=oi_detail,
            raw_value=oi_raw,
        ))
        
        # === Factor 3: 多空比分析 ===
        ls_score, ls_label, ls_detail, ls_raw = self._analyze_long_short(
            market_data.get('ls_ratio', 1.0),
            market_data.get('long_pct', 50),
            market_data.get('short_pct', 50),
        )
        factors.append(FactorScore(
            name="多空比",
            score=ls_score,
            weight=0.25,
            label=ls_label,
            detail=ls_detail,
            raw_value=ls_raw,
        ))
        
        # === Factor 4: 爆仓结构分析 ===
        liq_score, liq_label, liq_detail, liq_raw = self._analyze_liquidation(
            market_data.get('liq_total_24h', 0),
            market_data.get('liq_long_24h', 0),
            market_data.get('liq_short_24h', 0),
        )
        factors.append(FactorScore(
            name="爆仓结构",
            score=liq_score,
            weight=0.15,
            label=liq_label,
            detail=liq_detail,
            raw_value=liq_raw,
        ))
        
        # === Factor 5: 价格动量 ===
        mom_score, mom_label, mom_detail, mom_raw = self._analyze_momentum(
            market_data.get('btc_change_pct', 0),
            market_data.get('funding_rate', 0),
            market_data.get('ls_ratio', 1.0),
        )
        factors.append(FactorScore(
            name="价格动量",
            score=mom_score,
            weight=0.15,
            label=mom_label,
            detail=mom_detail,
            raw_value=mom_raw,
        ))
        
        # === 综合评分 ===
        overall = sum(f.score * f.weight for f in factors)
        confidence = self._calc_confidence(factors)
        
        # === 信号判定 ===
        signal, signal_label, risk = self._determine_signal(overall, confidence, factors)
        
        # === 生成总结 ===
        summary = self._generate_summary(signal, factors, overall)
        
        return AnalysisResult(
            symbol=symbol,
            signal=signal,
            signal_label=signal_label,
            confidence=confidence,
            overall_score=overall,
            factors=factors,
            summary=summary,
            risk_level=risk,
        )
    
    def _analyze_funding_rate(self, fr: float, annual: float) -> Tuple[float, str, str, dict]:
        """分析资金费率"""
        raw = {"fr": fr, "annual_pct": annual}
        
        # 年化资金费率
        annual_pct = annual if annual != 0 else fr * 3 * 365
        
        # 极度看多: 年化 > 60%
        if annual_pct > 0.06:
            score = -80  # 负分表示做空信号 (高资金费率意味着多方持续给空方付费,极端后容易反转)
            label = SignalLevel.EXTREME_BEAR.value
            detail = f"资金费率极度异常(年化 {annual_pct*100:.1f}%)，多方持续支付巨额资金费，可能是顶部信号"
        # 极度看空: 年化 < -60%
        elif annual_pct < -0.06:
            score = +80  # 极端空头资金费率 → 做多信号
            label = SignalLevel.EXTREME_BULL.value
            detail = f"资金费率为负且极端(年化 {annual_pct*100:.1f}%)，空方持续支付资金费，极端看多信号"
        # 看多: 年化 > 36%
        elif annual_pct > 0.01:
            score = -30
            label = SignalLevel.BEAR.value
            detail = f"资金费率偏高(年化 {annual_pct*100:.1f}%)，多方需持续支付资金费，短期偏空"
        # 看空: 年化 < -36%
        elif annual_pct < -0.01:
            score = +30
            label = SignalLevel.BULL.value
            detail = f"资金费率为负(年化 {annual_pct*100:.1f}%)，空方支付资金费，短期偏多"
        # 中性
        else:
            score = 0
            label = SignalLevel.NEUTRAL.value
            detail = f"资金费率正常({fr*100:.4f}%)，中性区域"
        
        return score, label, detail, raw
    
    def _analyze_open_interest(self, oi: float, oi_prev: float, price_chg: float) -> Tuple[float, str, str, dict]:
        """分析持仓量变化"""
        if oi_prev <= 0 or oi <= 0:
            return 0, SignalLevel.NEUTRAL.value, "数据不足", {}
        
        oi_change = (oi - oi_prev) / oi_prev
        raw = {"oi": oi, "oi_prev": oi_prev, "change_pct": oi_change}
        
        # 持仓量+价格同涨 → 多头趋势确认 (+分)
        if oi_change > self.OI_CHANGE_THRESHOLD and price_chg > 0:
            score = +40
            label = SignalLevel.BULL.value
            detail = f"持仓量暴增(+{oi_change*100:.1f}%)，价格同步上涨，多头强势"
        # 持仓量+价格同跌 → 空头趋势确认 (-分)
        elif oi_change > self.OI_CHANGE_THRESHOLD and price_chg < 0:
            score = -40
            label = SignalLevel.BEAR.value
            detail = f"持仓量暴增(+{oi_change*100:.1f}%)，价格同步下跌，空头强势"
        # 价格涨，持仓量降 → 警惕！可能见顶
        elif oi_change < -0.05 and price_chg > 0:
            score = -50
            label = SignalLevel.EXTREME_BEAR.value
            detail = f"价格上涨但持仓量下降({oi_change*100:.1f}%)，多头平仓，可能见顶预警"
        # 价格跌，持仓量降 → 可能见底
        elif oi_change < -0.05 and price_chg < 0:
            score = +50
            label = SignalLevel.EXTREME_BULL.value
            detail = f"价格下跌但持仓量减少({oi_change*100:.1f}%)，空头平仓，可能见底信号"
        # 持仓量大幅增加但价格平稳 → 积累信号
        elif oi_change > 0.08:
            score = +15
            label = SignalLevel.BULL.value
            detail = f"持仓量持续增加(+{oi_change*100:.1f}%)，市场在积累"
        # 持仓量大幅下降
        elif oi_change < -0.10:
            score = -20
            label = SignalLevel.BEAR.value
            detail = f"持仓量大幅下降({oi_change*100:.1f}%)，趋势可能反转"
        else:
            score = 0
            label = SignalLevel.NEUTRAL.value
            detail = f"持仓量稳定({oi_change*100:+.1f}%)，中性"
        
        return score, label, detail, raw
    
    def _analyze_long_short(self, ls_ratio: float, long_pct: float, short_pct: float) -> Tuple[float, str, str, dict]:
        """分析多空比"""
        raw = {"ratio": ls_ratio, "long_pct": long_pct, "short_pct": short_pct}
        
        # 极度看多: 多空比 > 1.5
        if ls_ratio > self.LS_THRESHOLD_BULL:
            score = -60  # 多头极端 → 反转风险
            label = SignalLevel.EXTREME_BEAR.value
            detail = f"多空比极度失衡({ls_ratio:.2f})，多头 {long_pct:.1f}% 主导，极端反转风险"
        # 极度看空: 多空比 < 0.5
        elif ls_ratio < self.LS_THRESHOLD_BEAR:
            score = +60  # 空头极端 → 反转信号
            label = SignalLevel.EXTREME_BULL.value
            detail = f"多空比极度失衡({ls_ratio:.2f})，空头 {short_pct:.1f}% 主导，极端做多信号"
        # 偏多: 多空比 > 1.1
        elif ls_ratio > 1.1:
            score = -20
            label = SignalLevel.BEAR.value
            detail = f"多空比偏多({ls_ratio:.2f})，多头略占优势"
        # 偏空: 多空比 < 0.9
        elif ls_ratio < 0.9:
            score = +20
            label = SignalLevel.BULL.value
            detail = f"多空比偏空({ls_ratio:.2f})，空头略占优势"
        else:
            score = 0
            label = SignalLevel.NEUTRAL.value
            detail = f"多空比平衡({ls_ratio:.2f})，多空均衡"
        
        return score, label, detail, raw
    
    def _analyze_liquidation(self, total: float, long_liq: float, short_liq: float) -> Tuple[float, str, str, dict]:
        """分析爆仓结构"""
        if total <= 0:
            return 0, SignalLevel.NEUTRAL.value, "无爆仓数据", {}
        
        short_ratio = short_liq / total if total > 0 else 0.5
        raw = {"total": total, "short_ratio": short_ratio}
        
        # 极度异常爆仓
        if total > self.LIQ_EXTREME_THRESHOLD:
            if short_ratio > 0.90:
                score = +40
                label = SignalLevel.BULL.value
                detail = f"爆仓极度异常($122M)，空头爆仓占{short_ratio*100:.0f}%，空头被清洗，看多"
            elif short_ratio < 0.10:
                score = -40
                label = SignalLevel.BEAR.value
                detail = f"多头爆仓占{short_ratio*100:.0f}%，极端异常"
            else:
                score = 0
                label = SignalLevel.NEUTRAL.value
                detail = f"爆仓量巨大($122M)，多空双杀"
        # 正常爆仓
        elif short_ratio > 0.85:
            score = +20
            label = SignalLevel.BULL.value
            detail = f"空头爆仓为主({short_ratio*100:.0f}%)，空头被清洗"
        elif short_ratio < 0.40:
            score = -20
            label = SignalLevel.BEAR.value
            detail = f"多头爆仓为主({short_ratio*100:.0f}%)，警惕"
        else:
            score = 0
            label = SignalLevel.NEUTRAL.value
            detail = f"爆仓结构正常，空头{short_ratio*100:.0f}% / 多头{(1-short_ratio)*100:.0f}%"
        
        return score, label, detail, raw
    
    def _analyze_momentum(self, price_chg: float, fr: float, ls_ratio: float) -> Tuple[float, str, str, dict]:
        """分析价格动量"""
        raw = {"price_chg": price_chg, "fr": fr, "ls_ratio": ls_ratio}
        
        # 极端上涨
        if price_chg > 5:
            # 配合空头主导 → 反弹可能强劲
            if ls_ratio < 0.7:
                score = +30
                label = SignalLevel.BULL.value
                detail = f"价格暴涨(+{price_chg:.1f}%)+空头主导，反弹动力强劲"
            else:
                score = -20
                label = SignalLevel.BEAR.value
                detail = f"价格暴涨(+{price_chg:.1f}%)，但多头也大量参与，追高风险"
        # 极端下跌
        elif price_chg < -5:
            if ls_ratio > 1.3:
                score = -30
                label = SignalLevel.BEAR.value
                detail = f"价格暴跌({price_chg:.1f}%)+多头主导，可能继续下行"
            else:
                score = +10
                label = SignalLevel.BULL.value
                detail = f"价格下跌({price_chg:.1f}%)，空头主导，可能是洗盘"
        # 温和上涨
        elif price_chg > 1:
            score = +10
            label = SignalLevel.BULL.value
            detail = f"价格温和上涨(+{price_chg:.1f}%)"
        # 温和下跌
        elif price_chg < -1:
            score = -10
            label = SignalLevel.BEAR.value
            detail = f"价格温和下跌({price_chg:.1f}%)"
        else:
            score = 0
            label = SignalLevel.NEUTRAL.value
            detail = f"价格相对平稳({price_chg:+.1f}%)"
        
        return score, label, detail, raw
    
    def _calc_confidence(self, factors: List[FactorScore]) -> float:
        """计算信号置信度"""
        # 因子越多，置信度越高
        active_factors = [f for f in factors if abs(f.score) > 0]
        base = len(active_factors) * 12
        
        # 极端值加分
        extreme_count = sum(1 for f in factors if abs(f.score) >= 60)
        extreme_bonus = extreme_count * 15
        
        # 方向一致性加分
        positive = sum(1 for f in factors if f.score > 0)
        negative = sum(1 for f in factors if f.score < 0)
        consensus = max(positive, negative)
        consensus_bonus = (consensus - 2) * 5 if consensus >= 2 else 0
        
        confidence = min(100, base + extreme_bonus + consensus_bonus)
        return round(confidence, 1)
    
    def _determine_signal(self, overall: float, confidence: float, factors: List[FactorScore]) -> Tuple[Signal, str, str]:
        """综合判定信号"""
        # 风险评估
        extreme_count = sum(1 for f in factors if abs(f.score) >= 60)
        if extreme_count >= 3:
            risk = "极高"
        elif extreme_count >= 2:
            risk = "高"
        elif extreme_count >= 1:
            risk = "中"
        else:
            risk = "低"
        
        # 分数判定
        if overall >= 50:
            return Signal.STRONG_BUY, SignalLevel.EXTREME_BULL.value, risk
        elif overall >= 20:
            return Signal.BUY, SignalLevel.BULL.value, risk
        elif overall <= -50:
            return Signal.STRONG_SELL, SignalLevel.EXTREME_BEAR.value, risk
        elif overall <= -20:
            return Signal.SELL, SignalLevel.BEAR.value, risk
        else:
            return Signal.NEUTRAL, SignalLevel.NEUTRAL.value, risk
    
    def _generate_summary(self, signal: Signal, factors: List[FactorScore], overall: float) -> str:
        """生成分析总结"""
        positive = sum(1 for f in factors if f.score > 0)
        negative = sum(1 for f in factors if f.score < 0)
        
        if signal == Signal.STRONG_BUY:
            return f"综合评分 {overall:.1f}，{positive}个看多/{negative}个看空因子，极度看多信号，建议关注做多机会"
        elif signal == Signal.BUY:
            return f"综合评分 {overall:.1f}，偏多信号，{positive}个因子支持上涨，可考虑轻仓做多"
        elif signal == Signal.STRONG_SELL:
            return f"综合评分 {overall:.1f}，{negative}个看空/{positive}个看多因子，极度看空信号，建议回避或做空"
        elif signal == Signal.SELL:
            return f"综合评分 {overall:.1f}，偏空信号，{negative}个因子支持下跌，注意回调风险"
        else:
            return f"综合评分 {overall:.1f}，多空信号均衡({positive}/{negative})，建议观望"


# ==================== 异步封装 ====================
class AsyncSignalAnalyzer:
    """异步信号分析 - 支持实时数据流"""
    
    def __init__(self):
        self.sync_analyzer = SignalAnalyzer()
    
    async def analyze_realtime(self, btc_data: dict, deriv_data: dict) -> AnalysisResult:
        """实时分析 - 接收 Binance + Coinglass 数据"""
        market_data = {
            "symbol": "BTC",
            "btc_price": btc_data.get('price', 0),
            "btc_change_pct": btc_data.get('change_pct', 0),
            "funding_rate": deriv_data.get('funding_rate', 0),
            "annual_rate": deriv_data.get('annual_rate', 0),
            "open_interest_usd": deriv_data.get('open_interest_usd', 0),
            "liq_total_24h": deriv_data.get('liquidation_24h', {}).get('total_usd', 0),
            "liq_long_24h": deriv_data.get('liquidation_24h', {}).get('long_usd', 0),
            "liq_short_24h": deriv_data.get('liquidation_24h', {}).get('short_usd', 0),
            "long_pct": deriv_data.get('long_short', {}).get('long_pct', 50),
            "short_pct": deriv_data.get('long_short', {}).get('short_pct', 50),
            "ls_ratio": deriv_data.get('long_short', {}).get('ratio', 1.0),
        }
        return self.sync_analyzer.analyze(market_data)


# 全局单例
_analyzer = None

def get_signal_analyzer() -> SignalAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SignalAnalyzer()
    return _analyzer
