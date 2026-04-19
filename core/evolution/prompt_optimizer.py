"""
提示词优化器 (Prompt Optimizer)
分析历史提示词效果，自动优化生成更有效的提示词
"""
import sqlite3
import json
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from core.utils.logger import logger
from core.utils.helpers import safe_execute


@dataclass
class PromptTemplate:
    """提示词模板"""
    id: str
    name: str
    template: str           # 模板文本
    variables: List[str]   # 变量列表
    version: int
    created_at: int
    success_count: int = 0
    failure_count: int = 0
    total_usage: int = 0
    avg_score: float = 0.0

    def win_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0


@dataclass
class PromptPerformance:
    """单次提示词表现"""
    id: str
    template_id: str
    symbol: str
    timeframe: str
    prompt_text: str
    response_text: str
    final_score: float      # 最终评分
    predicted_signal: str
    actual_outcome: str     # SUCCESS / FAILURE / PENDING
    actual_profit: float
    processing_time: float  # 秒
    tokens_used: int
    created_at: int
    latency_score: float    # 延迟评分 0-100

    def to_dict(self) -> Dict:
        return asdict(self)


class PromptOptimizer:
    """
    提示词优化器
    1. 追踪提示词使用效果
    2. 分析关键词/结构对效果的影响
    3. 生成优化建议
    4. A/B测试支持
    """

    # 基础提示词模板
    DEFAULT_TEMPLATES = {
        "analysis": """你是一个专业的加密货币技术分析师。请分析 {symbol} 在 {timeframe} 周期上的交易信号。

当前市场数据：
- RSI(14): {rsi}
- MACD柱状: {macd_hist}
- 布林带位置: {bb_pos}%
- 趋势: {trend}

资金费率: {funding_rate}% (年化 {funding_annual}%)

请给出：
1. 交易信号 (BUY/SELL/NEUTRAL)
2. 置信度 (0-100%)
3. 主要理由 (3点)
4. 风险提示
5. 入场区间和止损位建议""",

        "pattern": """分析 {symbol} 的K线形态。

最近K线数据（{num_candles}根）：
{candles_text}

当前价格：{price}

请识别：
1. 主要形态（如果有）
2. 支撑位和阻力位
3. 短期趋势判断
4. 交易建议""",

        "multi_factor": """作为加密货币量化分析师，分析 {symbol} 的综合信号。

维度1 - 技术面：
RSI: {rsi} | MACD: {macd} | 布林: {bb_pos}%

维度2 - 资金面：
资金费率: {funding_rate}% | 持仓量变化: {oi_change}%

维度3 - 情绪面：
多空比: {ls_ratio} | 24h爆仓: ${liquidations}

维度4 - 链上数据：
Gas: {gas} Gwei | Mempool: {mempool_tx}笔

综合判断：""",
    }

    def __init__(self, db_path: str = None):
        if db_path is None:
            import os
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base, "data", "prompt_optimizer.db")
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

        # 模板表
        c.execute("""
            CREATE TABLE IF NOT EXISTS prompt_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                template TEXT NOT NULL,
                variables TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                created_at INTEGER NOT NULL,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                total_usage INTEGER DEFAULT 0,
                avg_score REAL DEFAULT 0.0,
                is_active INTEGER DEFAULT 1
            )
        """)

        # 性能记录表
        c.execute("""
            CREATE TABLE IF NOT EXISTS prompt_performances (
                id TEXT PRIMARY KEY,
                template_id TEXT,
                symbol TEXT NOT NULL,
                timeframe TEXT,
                prompt_text TEXT,
                response_text TEXT,
                final_score REAL,
                predicted_signal TEXT,
                actual_outcome TEXT,
                actual_profit REAL,
                processing_time REAL,
                tokens_used INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL,
                latency_score REAL DEFAULT 100.0,
                FOREIGN KEY(template_id) REFERENCES prompt_templates(id)
            )
        """)

        # 关键词效果表
        c.execute("""
            CREATE TABLE IF NOT EXISTS keyword_effects (
                keyword TEXT PRIMARY KEY,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                avg_success_score REAL DEFAULT 0.0,
                total_mentions INTEGER DEFAULT 0
            )
        """)

        # 创建索引
        c.execute("CREATE INDEX IF NOT EXISTS idx_tp_outcome ON prompt_performances(actual_outcome)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tp_template ON prompt_performances(template_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tp_symbol ON prompt_performances(symbol)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tp_created ON prompt_performances(created_at)")

        conn.commit()

        # 插入默认模板
        self._insert_default_templates()
        logger.info(f"提示词优化器初始化: {self.db_path}")

    def _insert_default_templates(self):
        conn = self._get_conn()
        c = conn.cursor()

        for name, template in self.DEFAULT_TEMPLATES.items():
            c.execute("SELECT id FROM prompt_templates WHERE name = ?", (name,))
            if not c.fetchone():
                import re
                variables = re.findall(r'\{(\w+)\}', template)
                template_id = hashlib.md5(name.encode()).hexdigest()[:12]
                c.execute("""
                    INSERT INTO prompt_templates
                    (id, name, template, variables, version, created_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                """, (template_id, name, template, json.dumps(variables), int(time.time())))

        conn.commit()

    def record_performance(
        self,
        template_id: str,
        symbol: str,
        timeframe: str,
        prompt_text: str,
        response_text: str,
        predicted_signal: str,
        processing_time: float,
        tokens_used: int = 0,
        actual_outcome: str = "PENDING",
        actual_profit: float = 0.0,
        final_score: float = 0.0,
    ) -> str:
        """记录一次提示词执行效果"""
        conn = self._get_conn()
        c = conn.cursor()

        perf_id = hashlib.sha1(f"{prompt_text[:100]}{time.time()}".encode()).hexdigest()[:16]
        created_at = int(time.time())

        # 计算延迟评分 (越快越好)
        latency_score = max(0, 100 - processing_time * 2) if processing_time < 60 else 0

        c.execute("""
            INSERT INTO prompt_performances (
                id, template_id, symbol, timeframe, prompt_text, response_text,
                final_score, predicted_signal, actual_outcome, actual_profit,
                processing_time, tokens_used, created_at, latency_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            perf_id, template_id, symbol, timeframe, prompt_text, response_text,
            final_score, predicted_signal, actual_outcome, actual_profit,
            processing_time, tokens_used, created_at, latency_score
        ))

        # 更新模板统计
        if actual_outcome != "PENDING":
            if actual_outcome == "SUCCESS":
                c.execute("""
                    UPDATE prompt_templates
                    SET success_count = success_count + 1,
                        total_usage = total_usage + 1,
                        avg_score = (avg_score * success_count + ?) / (success_count + 1)
                    WHERE id = ?
                """, (final_score, template_id))
            elif actual_outcome == "FAILURE":
                c.execute("""
                    UPDATE prompt_templates
                    SET failure_count = failure_count + 1,
                        total_usage = total_usage + 1
                    WHERE id = ?
                """, (template_id,))

        # 提取关键词效果
        self._extract_keyword_effects(prompt_text, actual_outcome, final_score)

        conn.commit()
        return perf_id

    def _extract_keyword_effects(self, prompt: str, outcome: str, score: float):
        """提取和更新关键词效果"""
        conn = self._get_conn()
        c = conn.cursor()

        keywords = [
            "RSI", "MACD", "布林带", "支撑位", "阻力位",
            "资金费率", "持仓量", "多空比", "爆仓",
            "趋势", "反转", "突破", "回踩",
            "止损", "止盈", "仓位", "杠杆",
            "买入", "卖出", "做多", "做空",
        ]

        for kw in keywords:
            if kw in prompt:
                c.execute("""
                    INSERT INTO keyword_effects (keyword, total_mentions)
                    VALUES (?, 1)
                    ON CONFLICT(keyword) DO UPDATE SET
                        total_mentions = total_mentions + 1
                """, (kw,))

                if outcome == "SUCCESS":
                    c.execute("""
                        UPDATE keyword_effects
                        SET success_count = success_count + 1,
                            avg_success_score = (avg_success_score * success_count + ?) / (success_count + 1)
                        WHERE keyword = ?
                    """, (score, kw))
                elif outcome == "FAILURE":
                    c.execute("""
                        UPDATE keyword_effects
                        SET failure_count = failure_count + 1
                        WHERE keyword = ?
                    """, (kw,))

        conn.commit()

    def get_template_stats(self, template_id: str) -> Dict:
        """获取模板统计"""
        conn = self._get_conn()
        c = conn.cursor()

        c.execute("SELECT * FROM prompt_templates WHERE id = ?", (template_id,))
        row = c.fetchone()
        if not row:
            return {"error": "模板不存在"}

        row = dict(row)
        total = row["success_count"] + row["failure_count"]
        win_rate = row["success_count"] / total if total > 0 else 0.0

        # 最近表现（最近30条）
        c.execute("""
            SELECT actual_outcome, final_score, latency_score, created_at
            FROM prompt_performances
            WHERE template_id = ?
            ORDER BY created_at DESC
            LIMIT 30
        """, (template_id,))
        recent = c.fetchall()
        recent_outcomes = [dict(r) for r in recent]

        # 趋势分析
        recent_success = sum(1 for r in recent_outcomes if r["actual_outcome"] == "SUCCESS")
        recent_win_rate = recent_success / len(recent_outcomes) if recent_outcomes else 0

        # 按信号分析
        c.execute("""
            SELECT predicted_signal, actual_outcome, COUNT(*) as count
            FROM prompt_performances
            WHERE template_id = ? AND actual_outcome != 'PENDING'
            GROUP BY predicted_signal, actual_outcome
        """, (template_id,))
        signal_breakdown = [dict(r) for r in c.fetchall()]

        return {
            "template_id": row["id"],
            "name": row["name"],
            "version": row["version"],
            "success_count": row["success_count"],
            "failure_count": row["failure_count"],
            "total_usage": row["total_usage"],
            "win_rate": round(win_rate * 100, 1),
            "avg_score": round(row["avg_score"], 2),
            "recent_win_rate": round(recent_win_rate * 100, 1),
            "signal_breakdown": signal_breakdown,
            "recent_performance": recent_outcomes[:5],
            "trend": "improving" if recent_win_rate > win_rate else "declining" if recent_win_rate < win_rate - 0.1 else "stable",
        }

    def analyze_keyword_effects(self) -> List[Dict]:
        """分析关键词效果"""
        conn = self._get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT keyword, success_count, failure_count,
                   avg_success_score, total_mentions
            FROM keyword_effects
            WHERE total_mentions >= 3
            ORDER BY (success_count * 1.0 / total_mentions) DESC
        """)

        results = []
        for row in c.fetchall():
            d = dict(row)
            total = d["success_count"] + d["failure_count"]
            win_rate = d["success_count"] / total if total > 0 else 0
            results.append({
                "keyword": d["keyword"],
                "win_rate": round(win_rate * 100, 1),
                "success_count": d["success_count"],
                "failure_count": d["failure_count"],
                "total_mentions": d["total_mentions"],
                "avg_score": round(d["avg_success_score"], 1),
                "effectiveness": "high" if win_rate > 0.7 else "medium" if win_rate > 0.5 else "low",
            })

        return results

    def generate_optimized_prompt(
        self,
        template_name: str,
        context: Dict,
    ) -> Tuple[str, str]:
        """
        生成优化后的提示词
        返回: (prompt_text, improvement_notes)
        """
        conn = self._get_conn()
        c = conn.cursor()

        # 获取模板
        c.execute("SELECT * FROM prompt_templates WHERE name = ? AND is_active = 1", (template_name,))
        row = c.fetchone()
        if not row:
            return "", "模板不存在"

        template = dict(row)
        tmpl_text = template["template"]

        # 分析关键词效果
        keyword_effects = self.analyze_keyword_effects()
        high_effect_kws = [k["keyword"] for k in keyword_effects if k["effectiveness"] == "high"]
        low_effect_kws = [k["keyword"] for k in keyword_effects if k["effectiveness"] == "low"]

        # 构建提示词
        try:
            prompt = tmpl_text.format(**context)
        except KeyError as e:
            return "", f"缺少变量: {e}"

        # 添加优化注释（内部用）
        improvements = []

        if high_effect_kws:
            improvements.append(f"✅ 高效关键词: {', '.join(high_effect_kws[:5])}")
        if low_effect_kws:
            improvements.append(f"⚠️ 低效关键词: {', '.join(low_effect_kws[:3])}")

        # 性能提示
        stats = self.get_template_stats(template["id"])
        if stats.get("trend") == "improving":
            improvements.append(f"📈 模板趋势向好，胜率: {stats['recent_win_rate']}%")
        elif stats.get("trend") == "declining":
            improvements.append(f"📉 模板趋势下滑，建议优化")

        improvement_text = "\n".join(improvements) if improvements else ""

        return prompt, improvement_text

    def get_all_templates(self) -> List[Dict]:
        """获取所有模板"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT id, name, version, success_count, failure_count,
                   total_usage, avg_score, created_at
            FROM prompt_templates
            WHERE is_active = 1
            ORDER BY total_usage DESC
        """)
        results = []
        for row in c.fetchall():
            d = dict(row)
            total = d["success_count"] + d["failure_count"]
            d["win_rate"] = round(d["success_count"] / total * 100, 1) if total > 0 else 0
            d["variables"] = json.loads(
                c.execute("SELECT variables FROM prompt_templates WHERE id = ?", (d["id"],)).fetchone()[0]
            ) if False else []  # 简化
            results.append(d)
        return results

    def get_overall_stats(self) -> Dict:
        """整体统计"""
        conn = self._get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT
                COUNT(*) as total_templates,
                SUM(total_usage) as total_uses,
                SUM(success_count) as total_successes,
                SUM(failure_count) as total_failures
            FROM prompt_templates
        """)
        stats = dict(c.fetchone())

        total = stats["total_successes"] + stats["total_failures"]
        return {
            "total_templates": stats["total_templates"] or 0,
            "total_uses": stats["total_uses"] or 0,
            "total_successes": stats["total_successes"] or 0,
            "total_failures": stats["total_failures"] or 0,
            "overall_win_rate": round(
                stats["total_successes"] / total * 100, 1
            ) if total > 0 else 0.0,
        }

    @safe_execute(default=None)
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
