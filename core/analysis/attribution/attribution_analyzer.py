"""
归因分析模块 - 交易成败因子归因
五维因子分析：
1. 技术面因子 - RSI/MACD/均线等技术指标
2. 基本面因子 - 资金费率/持仓量等
3. 情绪面因子 - 新闻情感/市场情绪
4. 执行因子 - 入场时机/价格滑点
5. 风控因子 - 仓位管理/止损设置
"""
import sqlite3
import json
import time
from typing import Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from core.utils.logger import logger
from core.utils.helpers import safe_execute


# ─────────────────────────────────────────────────────────────
# 五维因子定义
# ─────────────────────────────────────────────────────────────
@dataclass
class AttributionFactor:
    """单个归因因子"""
    name: str
    category: str          # technical/fundamental/sentiment/execution/risk
    value: Any
    score: float           # -1.0 到 +1.0
    contribution: float     # 对结果的贡献度 %
    description: str
    verdict: str           # 正面/负面/中性


@dataclass
class AttributionResult:
    """完整归因结果"""
    trade_id: str
    symbol: str
    trade_direction: str    # LONG/SHORT
    profit_pct: float

    # 五维评分
    technical_score: float   # 技术面 0-100
    fundamental_score: float  # 基本面 0-100
    sentiment_score: float   # 情绪面 0-100
    execution_score: float   # 执行面 0-100
    risk_score: float        # 风控面 0-100
    overall_score: float     # 综合 0-100

    # 因子列表
    factors: list[AttributionFactor]

    # Top关键因子
    top_positive_factors: list[str]
    top_negative_factors: list[str]

    # 成功/失败判定
    verdict: str             # SUCCESS / FAILURE / PARTIAL
    primary_cause: str       # 主要原因
    improvement_suggestion: str  # 改进建议


class AttributionAnalyzer:
    """
    归因分析器 - 分解交易成败的五大因子

    分析维度：
    1. 技术面 - 指标信号质量、入场时机、趋势配合度
    2. 基本面 - 资金费率偏离、持仓量变化、流动性
    3. 情绪面 - 新闻情感、市场恐惧贪婪、社交情绪
    4. 执行面 - 入场价格、滑点、执行延迟
    5. 风控面 - 仓位大小、止损设置、杠杆率
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            import os
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base, "data", "attribution.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS attribution_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE,
                symbol TEXT,
                trade_direction TEXT,
                profit_pct REAL,
                technical_score REAL,
                fundamental_score REAL,
                sentiment_score REAL,
                execution_score REAL,
                risk_score REAL,
                overall_score REAL,
                factors_json TEXT,
                top_positive TEXT,
                top_negative TEXT,
                verdict TEXT,
                primary_cause TEXT,
                improvement TEXT,
                created_at INTEGER
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_attr_symbol ON attribution_results(symbol)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_attr_verdict ON attribution_results(verdict)")
        conn.commit()
        logger.info(f"归因分析库初始化: {self.db_path}")

    # ─────────────────────────────────────────────────────────
    # 因子评分计算
    # ─────────────────────────────────────────────────────────
    def _score_technical(self, data: dict) -> tuple[float, list[AttributionFactor]]:
        """技术面评分"""
        factors = []
        score_sum = 0
        count = 0

        # RSI 评分
        rsi = data.get('rsi', 50)
        if 30 < rsi < 70:
            rsi_score = 0.7
            rsi_desc = f"RSI={rsi:.0f} 适中区域"
            rsi_verdict = "正面"
        elif 20 < rsi < 30 or 70 < rsi < 80:
            rsi_score = 0.5
            rsi_desc = f"RSI={rsi:.0f} 偏极端"
            rsi_verdict = "中性"
        else:
            rsi_score = 0.2
            rsi_desc = f"RSI={rsi:.0f} 极度极端"
            rsi_verdict = "负面"
            score_sum += rsi_score
            count += 1

        factors.append(AttributionFactor(
            name="RSI指标",
            category="technical",
            value=f"{rsi:.0f}",
            score=rsi_score,
            contribution=10,
            description=rsi_desc,
            verdict=rsi_verdict,
        ))

        # 趋势评分
        trend = data.get('trend', 'SIDEWAYS')
        signal = data.get('signal', 'NEUTRAL')
        if trend == 'UP' and signal == 'BUY':
            trend_score = 0.9
            trend_verdict = "正面"
        elif trend == 'DOWN' and signal == 'SELL':
            trend_score = 0.9
            trend_verdict = "正面"
        elif trend == 'SIDEWAYS':
            trend_score = 0.4
            trend_verdict = "负面"
        else:
            trend_score = 0.3
            trend_verdict = "负面"

        factors.append(AttributionFactor(
            name="趋势+信号配合",
            category="technical",
            value=f"{trend}/{signal}",
            score=trend_score,
            contribution=20,
            description=f"趋势{trend}与信号{signal}配合度",
            verdict=trend_verdict,
        ))

        # MACD
        macd_hist = data.get('macd_histogram', 0)
        if abs(macd_hist) > 0:
            macd_score = 0.8 if macd_hist > 0 else 0.5
            macd_desc = f"MACD柱状图={macd_hist:.4f}"
        else:
            macd_score = 0.4
            macd_desc = "MACD柱状图=0"

        factors.append(AttributionFactor(
            name="MACD动量",
            category="technical",
            value=macd_hist,
            score=macd_score,
            contribution=15,
            description=macd_desc,
            verdict="正面" if macd_score > 0.6 else "中性",
        ))

        # 布林带位置
        bb_pos = data.get('bb_position', 50)
        if 30 < bb_pos < 70:
            bb_score = 0.7
            bb_verdict = "正面"
        elif bb_pos < 20:
            bb_score = 0.6
            bb_verdict = "中性"  # 接近下轨可反弹
        else:
            bb_score = 0.3
            bb_verdict = "负面"

        factors.append(AttributionFactor(
            name="布林带位置",
            category="technical",
            value=f"{bb_pos:.0f}%",
            score=bb_score,
            contribution=10,
            description=f"价格在布林带{bb_pos:.0f}%位置",
            verdict=bb_verdict,
        ))

        # EMA均线
        ema_9 = data.get('ema_9', 0)
        ema_20 = data.get('ema_20', 0)
        price = data.get('current_price', 0)
        if ema_9 > ema_20 and price > ema_9:
            ema_score = 0.8
            ema_verdict = "正面"
        elif ema_9 < ema_20 and price < ema_9:
            ema_score = 0.8
            ema_verdict = "正面"
        else:
            ema_score = 0.4
            ema_verdict = "负面"

        factors.append(AttributionFactor(
            name="EMA均线排列",
            category="technical",
            value=f"EMA9={ema_9} EMA20={ema_20}",
            score=ema_score,
            contribution=10,
            description="均线多头/空头排列状态",
            verdict=ema_verdict,
        ))

        for f in factors:
            score_sum += f.score
        avg = score_sum / len(factors) if factors else 0.5
        return avg * 100, factors

    def _score_fundamental(self, data: dict) -> tuple[float, list[AttributionFactor]]:
        """基本面评分"""
        factors = []
        score_sum = 0

        # 资金费率
        funding_rate = data.get('funding_rate', 0)
        if abs(funding_rate) < 0.01:
            fr_score = 0.8
            fr_desc = f"资金费率={funding_rate:.4f}% 中性"
            fr_verdict = "正面"
        elif funding_rate < -0.05:
            fr_score = 0.7  # 空头被付钱，看多反弹
            fr_desc = f"资金费率={funding_rate:.4f}% 负费率"
            fr_verdict = "正面"
        elif funding_rate > 0.05:
            fr_score = 0.3  # 多头被付钱，做空机会
            fr_desc = f"资金费率={funding_rate:.4f}% 正费率偏高"
            fr_verdict = "负面"
        else:
            fr_score = 0.5
            fr_desc = f"资金费率={funding_rate:.4f}%"
            fr_verdict = "中性"

        factors.append(AttributionFactor(
            name="资金费率",
            category="fundamental",
            value=f"{funding_rate:.4f}%",
            score=fr_score,
            contribution=25,
            description=fr_desc,
            verdict=fr_verdict,
        ))
        score_sum += fr_score

        # 持仓量变化
        oi_change = data.get('oi_change_pct', 0)
        if abs(oi_change) < 20:
            oi_score = 0.7
            oi_desc = f"持仓量变化={oi_change:.1f}% 稳定"
            oi_verdict = "正面"
        elif oi_change > 50:
            oi_score = 0.4
            oi_desc = f"持仓量变化={oi_change:.1f}% 大幅增加"
            oi_verdict = "中性"
        else:
            oi_score = 0.3
            oi_desc = f"持仓量变化={oi_change:.1f}% 大幅减少"
            oi_verdict = "负面"

        factors.append(AttributionFactor(
            name="持仓量变化",
            category="fundamental",
            value=f"{oi_change:.1f}%",
            score=oi_score,
            contribution=20,
            description=oi_desc,
            verdict=oi_verdict,
        ))
        score_sum += oi_score

        # 多空比
        ls_ratio = data.get('long_short_ratio', 1.0)
        if 0.8 < ls_ratio < 1.2:
            ls_score = 0.7
            ls_desc = f"多空比={ls_ratio:.2f} 平衡"
            ls_verdict = "正面"
        elif ls_ratio < 0.7:
            ls_score = 0.5
            ls_desc = f"多空比={ls_ratio:.2f} 空头占优"
            ls_verdict = "中性"
        else:
            ls_score = 0.5
            ls_desc = f"多空比={ls_ratio:.2f} 多头占优"
            ls_verdict = "中性"

        factors.append(AttributionFactor(
            name="多空比",
            category="fundamental",
            value=f"{ls_ratio:.2f}",
            score=ls_score,
            contribution=20,
            description=ls_desc,
            verdict=ls_verdict,
        ))
        score_sum += ls_score

        # 爆仓结构
        liq_dominant = data.get('liquidation_dominant', 'balanced')
        if liq_dominant == 'short':
            liq_score = 0.7  # 空头爆仓，看多
            liq_desc = "空头主导爆仓"
            liq_verdict = "正面"
        elif liq_dominant == 'long':
            liq_score = 0.4  # 多头爆仓
            liq_desc = "多头主导爆仓"
            liq_verdict = "负面"
        else:
            liq_score = 0.6
            liq_desc = "多空爆仓平衡"
            liq_verdict = "中性"

        factors.append(AttributionFactor(
            name="爆仓结构",
            category="fundamental",
            value=liq_dominant,
            score=liq_score,
            contribution=20,
            description=liq_desc,
            verdict=liq_verdict,
        ))
        score_sum += liq_score

        return score_sum / len(factors) * 100, factors

    def _score_sentiment(self, data: dict) -> tuple[float, list[AttributionFactor]]:
        """情绪面评分"""
        factors = []
        score_sum = 0

        news_sentiment = data.get('news_sentiment', 0)
        if news_sentiment > 0.2:
            ns_score = 0.8
            ns_verdict = "正面"
        elif news_sentiment < -0.2:
            ns_score = 0.3
            ns_verdict = "负面"
        else:
            ns_score = 0.6
            ns_verdict = "中性"

        factors.append(AttributionFactor(
            name="新闻情感",
            category="sentiment",
            value=news_sentiment,
            score=ns_score,
            contribution=40,
            description=f"新闻情感分数={news_sentiment:.3f}",
            verdict=ns_verdict,
        ))
        score_sum += ns_score

        # 市场恐惧/贪婪
        fear_greed = data.get('fear_greed', 50)
        if 30 < fear_greed < 70:
            fg_score = 0.6
            fg_verdict = "中性"
        elif fear_greed < 20:
            fg_score = 0.8  # 极度恐惧，可能反弹
            fg_verdict = "正面"
        elif fear_greed > 80:
            fg_score = 0.3  # 极度贪婪，可能回调
            fg_verdict = "负面"
        else:
            fg_score = 0.5
            fg_verdict = "中性"

        factors.append(AttributionFactor(
            name="恐惧贪婪指数",
            category="sentiment",
            value=fear_greed,
            score=fg_score,
            contribution=30,
            description=f"恐惧贪婪={fear_greed:.0f}",
            verdict=fg_verdict,
        ))
        score_sum += fg_score

        avg = score_sum / len(factors) if factors else 0.5
        return avg * 100, factors

    def _score_execution(self, data: dict) -> tuple[float, list[AttributionFactor]]:
        """执行面评分"""
        factors = []
        score_sum = 0

        # 入场时机 vs 信号评分
        confidence = data.get('confidence', 50)
        if confidence > 70:
            conf_score = 0.9
            conf_verdict = "正面"
        elif confidence > 50:
            conf_score = 0.7
            conf_verdict = "正面"
        elif confidence > 30:
            conf_score = 0.5
            conf_verdict = "中性"
        else:
            conf_score = 0.2
            conf_verdict = "负面"

        factors.append(AttributionFactor(
            name="信号置信度",
            category="execution",
            value=f"{confidence:.0f}%",
            score=conf_score,
            contribution=40,
            description=f"入场置信度={confidence:.0f}%",
            verdict=conf_verdict,
        ))
        score_sum += conf_score

        # 滑点
        slippage = data.get('slippage_pct', 0)
        if slippage < 0.1:
            slip_score = 0.9
            slip_verdict = "正面"
        elif slippage < 0.5:
            slip_score = 0.7
            slip_verdict = "正面"
        else:
            slip_score = 0.3
            slip_verdict = "负面"

        factors.append(AttributionFactor(
            name="价格滑点",
            category="execution",
            value=f"{slippage:.3f}%",
            score=slip_score,
            contribution=30,
            description=f"滑点={slippage:.3f}%",
            verdict=slip_verdict,
        ))
        score_sum += slip_score

        avg = score_sum / len(factors) if factors else 0.5
        return avg * 100, factors

    def _score_risk(self, data: dict) -> tuple[float, list[AttributionFactor]]:
        """风控评分"""
        factors = []
        score_sum = 0

        # 仓位大小 (假设风险敞口)
        position_size = data.get('position_size_pct', 10)
        if position_size <= 5:
            pos_score = 0.9
            pos_verdict = "正面"
        elif position_size <= 10:
            pos_score = 0.7
            pos_verdict = "正面"
        elif position_size <= 20:
            pos_score = 0.5
            pos_verdict = "中性"
        else:
            pos_score = 0.2
            pos_verdict = "负面"

        factors.append(AttributionFactor(
            name="仓位大小",
            category="risk",
            value=f"{position_size:.1f}%",
            score=pos_score,
            contribution=35,
            description=f"仓位={position_size:.1f}%账户",
            verdict=pos_verdict,
        ))
        score_sum += pos_score

        # 止损设置
        has_stop_loss = data.get('has_stop_loss', True)
        if has_stop_loss:
            sl_score = 0.8
            sl_verdict = "正面"
        else:
            sl_score = 0.2
            sl_verdict = "负面"

        factors.append(AttributionFactor(
            name="止损设置",
            category="risk",
            value="有" if has_stop_loss else "无",
            score=sl_score,
            contribution=35,
            description="是否设置止损",
            verdict=sl_verdict,
        ))
        score_sum += sl_score

        # 杠杆
        leverage = data.get('leverage', 1)
        if leverage <= 3:
            lev_score = 0.9
            lev_verdict = "正面"
        elif leverage <= 10:
            lev_score = 0.5
            lev_verdict = "中性"
        else:
            lev_score = 0.1
            lev_verdict = "负面"

        factors.append(AttributionFactor(
            name="杠杆倍数",
            category="risk",
            value=f"{leverage}x",
            score=lev_score,
            contribution=30,
            description=f"使用杠杆={leverage}x",
            verdict=lev_verdict,
        ))
        score_sum += lev_score

        avg = score_sum / len(factors) if factors else 0.5
        return avg * 100, factors

    # ─────────────────────────────────────────────────────────
    # 完整归因分析
    # ─────────────────────────────────────────────────────────
    @safe_execute(default=None)
    def analyze(
        self,
        trade_data: dict,
    ) -> AttributionResult:
        """
        执行完整五维归因分析
        trade_data 包含:
            - trade_id, symbol, direction
            - profit_pct, entry_price, exit_price
            - 技术指标: rsi, macd_histogram, bb_position, ema_9, ema_20, trend, signal
            - 基本面: funding_rate, oi_change_pct, long_short_ratio, liquidation_dominant
            - 情绪面: news_sentiment, fear_greed
            - 执行: confidence, slippage_pct
            - 风控: position_size_pct, has_stop_loss, leverage
        """
        all_factors = []
        profit_pct = trade_data.get('profit_pct', 0)
        is_success = profit_pct > 0

        # 五维评分
        tech_score, tech_factors = self._score_technical(trade_data)
        fund_score, fund_factors = self._score_fundamental(trade_data)
        sent_score, sent_factors = self._score_sentiment(trade_data)
        exec_score, exec_factors = self._score_execution(trade_data)
        risk_score, risk_factors = self._score_risk(trade_data)

        all_factors = tech_factors + fund_factors + sent_factors + exec_factors + risk_factors

        # 综合评分 (加权平均)
        weights = {"technical": 0.25, "fundamental": 0.25, "sentiment": 0.15, "execution": 0.20, "risk": 0.15}
        overall = (
            tech_score * weights["technical"] +
            fund_score * weights["fundamental"] +
            sent_score * weights["sentiment"] +
            exec_score * weights["execution"] +
            risk_score * weights["risk"]
        )

        # Top因子
        sorted_factors = sorted(all_factors, key=lambda x: x.score, reverse=True)
        top_positive = [f.name for f in sorted_factors[:3] if f.verdict == "正面"]
        top_negative = [f.name for f in sorted_factors[-3:] if f.verdict == "负面"]

        # 判定
        if overall >= 70:
            verdict = "SUCCESS"
        elif overall >= 40:
            verdict = "PARTIAL"
        else:
            verdict = "FAILURE"

        # 主要原因
        if top_negative:
            primary_cause = f"主要负面因子: {', '.join(top_negative[:2])}"
        elif top_positive:
            primary_cause = f"主要正面因子: {', '.join(top_positive[:2])}"
        else:
            primary_cause = "各因子贡献均衡"

        # 改进建议
        suggestions = []
        if tech_score < 50:
            suggestions.append("技术面信号不清晰，建议等待更好的技术入场点")
        if fund_score < 50:
            suggestions.append("基本面配合不佳，注意资金费率风险")
        if sent_score < 50:
            suggestions.append("市场情绪偏空，需谨慎")
        if exec_score < 50:
            suggestions.append("入场置信度不足，建议提高信号阈值")
        if risk_score < 50:
            suggestions.append("风控执行不到位，建议降低仓位或增加止损")

        improvement = " | ".join(suggestions) if suggestions else "各维度表现良好，保持当前策略"

        result = AttributionResult(
            trade_id=trade_data.get('trade_id', ''),
            symbol=trade_data.get('symbol', ''),
            trade_direction=trade_data.get('direction', 'LONG'),
            profit_pct=profit_pct,
            technical_score=round(tech_score, 1),
            fundamental_score=round(fund_score, 1),
            sentiment_score=round(sent_score, 1),
            execution_score=round(exec_score, 1),
            risk_score=round(risk_score, 1),
            overall_score=round(overall, 1),
            factors=all_factors,
            top_positive_factors=top_positive,
            top_negative_factors=top_negative,
            verdict=verdict,
            primary_cause=primary_cause,
            improvement_suggestion=improvement,
        )

        # 保存
        self._save_result(result)
        logger.info(
            f"归因分析: {result.trade_id} {result.symbol} "
            f"{result.verdict} {profit_pct:+.2f}% "
            f"综合={overall:.0f} | 主因: {primary_cause[:40]}"
        )

        return result

    def _save_result(self, result: AttributionResult):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO attribution_results (
                trade_id, symbol, trade_direction, profit_pct,
                technical_score, fundamental_score, sentiment_score,
                execution_score, risk_score, overall_score,
                factors_json, top_positive, top_negative,
                verdict, primary_cause, improvement, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.trade_id, result.symbol, result.trade_direction, result.profit_pct,
            result.technical_score, result.fundamental_score, result.sentiment_score,
            result.execution_score, result.risk_score, result.overall_score,
            json.dumps([asdict(f) for f in result.factors], ensure_ascii=False),
            json.dumps(result.top_positive_factors),
            json.dumps(result.top_negative_factors),
            result.verdict, result.primary_cause, result.improvement_suggestion,
            int(time.time()),
        ))
        conn.commit()

    def get_summary_report(self, symbol: str = None, days: int = 30) -> dict:
        """获取归因总结报告"""
        conn = self._get_conn()
        c = conn.cursor()
        cutoff = int(time.time()) - days * 86400
        sym_filter = f"AND symbol = '{symbol}'" if symbol else ""

        c.execute(f"""
            SELECT verdict, COUNT(*) cnt,
                   AVG(technical_score) tech,
                   AVG(fundamental_score) fund,
                   AVG(sentiment_score) sent,
                   AVG(execution_score) exec_,
                   AVG(risk_score) risk,
                   AVG(overall_score) overall,
                   AVG(profit_pct) avg_profit
            FROM attribution_results
            WHERE created_at > ? {sym_filter}
            GROUP BY verdict
        """, (cutoff,))

        rows = c.fetchall()
        by_verdict = {}
        total_cnt = 0
        for row in rows:
            by_verdict[row['verdict']] = {
                "count": row['cnt'],
                "avg_technical": round(row['tech'] or 0, 1),
                "avg_fundamental": round(row['fund'] or 0, 1),
                "avg_sentiment": round(row['sent'] or 0, 1),
                "avg_execution": round(row['exec_'] or 0, 1),
                "avg_risk": round(row['risk'] or 0, 1),
                "avg_overall": round(row['overall'] or 0, 1),
                "avg_profit": round(row['avg_profit'] or 0, 2),
            }
            total_cnt += row['cnt']

        return {
            "total_trades": total_cnt,
            "by_verdict": by_verdict,
            "period_days": days,
        }

    @safe_execute(default=None)
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


_attr: Optional[AttributionAnalyzer] = None


def get_attribution_analyzer() -> AttributionAnalyzer:
    global _attr
    if _attr is None:
        _attr = AttributionAnalyzer()
    return _attr
