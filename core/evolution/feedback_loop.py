"""
反馈循环系统 (Feedback Loop)
持续学习机制：自动收集结果 → 分析 → 优化 → 验证
驱动整个系统自进化
"""
import sqlite3
import json
import time
import asyncio
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from core.utils.logger import logger
from core.utils.helpers import safe_execute


@dataclass
class FeedbackEntry:
    """反馈条目"""
    id: str
    symbol: str
    timeframe: str

    # 信号
    signal: str
    signal_score: float
    confidence: float

    # 预测
    predicted_direction: str
    predicted_profit: float

    # 实际结果
    actual_direction: str
    actual_profit: float

    # 评估
    direction_correct: bool
    profit_correct: bool
    timing_score: float  # 0-100

    # 元数据
    model_id: str
    strategy_id: str
    created_at: int       # 信号时间
    resolved_at: int      # 结果时间
    feedback_score: float  # 综合反馈评分

    def to_dict(self) -> Dict:
        return asdict(self)


class FeedbackLoop:
    """
    反馈循环系统
    1. 持续收集交易信号和结果
    2. 自动评估预测准确性
    3. 触发知识库更新
    4. 触发策略进化
    5. 触发模型改进
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            import os
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base, "data", "feedback_loop.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

        # 回调函数
        self._callbacks: Dict[str, List[Callable]] = {
            "on_feedback": [],       # 每条反馈触发
            "on_pattern_found": [],  # 发现成功模式时
            "on_model_degrade": [],  # 模型表现下滑时
            "on_strategy_degrade": [],  # 策略表现下滑时
            "on_evolution_trigger": [],  # 触发进化时
        }

        # 滑动窗口统计
        self._window_size = 100  # 最近N条反馈

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
            CREATE TABLE IF NOT EXISTS feedback_entries (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                signal TEXT NOT NULL,
                signal_score REAL,
                confidence REAL,
                predicted_direction TEXT,
                predicted_profit REAL,
                actual_direction TEXT,
                actual_profit REAL,
                direction_correct INTEGER,
                profit_correct INTEGER,
                timing_score REAL,
                model_id TEXT,
                strategy_id TEXT,
                created_at INTEGER NOT NULL,
                resolved_at INTEGER,
                feedback_score REAL,
                notes TEXT DEFAULT ''
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS learning_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                symbol TEXT,
                description TEXT,
                data TEXT,
                triggered_by TEXT,
                actions_taken TEXT,
                result TEXT,
                created_at INTEGER NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS system_health (
                metric TEXT PRIMARY KEY,
                value REAL,
                threshold REAL,
                status TEXT,
                last_updated INTEGER
            )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_fb_symbol ON feedback_entries(symbol)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fb_created ON feedback_entries(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fb_resolved ON feedback_entries(resolved_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_learn_type ON learning_events(event_type)")

        conn.commit()
        logger.info(f"反馈循环系统初始化: {self.db_path}")

    # ── 核心API ──

    def record_signal(
        self,
        symbol: str,
        timeframe: str,
        signal: str,
        signal_score: float,
        confidence: float,
        predicted_direction: str,
        predicted_profit: float,
        model_id: str = "",
        strategy_id: str = "",
    ) -> str:
        """记录一条预测信号（等待结果）"""
        with self._lock:
            import hashlib
            entry_id = hashlib.sha1(
                f"{symbol}{signal}{time.time()}".encode()
            ).hexdigest()[:16]

            conn = self._get_conn()
            c = conn.cursor()
            now = int(time.time())

            c.execute("""
                INSERT INTO feedback_entries (
                    id, symbol, timeframe, signal, signal_score, confidence,
                    predicted_direction, predicted_profit, model_id, strategy_id,
                    created_at, feedback_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (entry_id, symbol, timeframe, signal, signal_score, confidence,
                  predicted_direction, predicted_profit, model_id, strategy_id, now))

            conn.commit()

            self._log_learning_event(
                "signal_recorded", symbol,
                f"记录信号: {signal} {symbol} {timeframe}",
                {"signal": signal, "score": signal_score, "predicted_profit": predicted_profit}
            )

            return entry_id

    def resolve_signal(
        self,
        entry_id: str,
        actual_direction: str,
        actual_profit: float,
        notes: str = "",
    ) -> FeedbackEntry:
        """
        记录信号结果，触发反馈分析
        这是核心方法：预测 vs 实际 → 反馈评分 → 触发学习
        """
        import hashlib
        with self._lock:
            conn = self._get_conn()
            c = conn.cursor()
            now = int(time.time())

            # 获取原始信号
            c.execute("SELECT * FROM feedback_entries WHERE id = ?", (entry_id,))
            row = c.fetchone()
            if not row:
                raise ValueError(f"信号不存在: {entry_id}")

            original = dict(row)

            # 计算评估
            direction_correct = 1 if actual_direction == original["predicted_direction"] else 0
            profit_correct = 1 if (actual_profit > 0) == (original["predicted_profit"] > 0) else 0

            # 时机评分（越接近预测利润越好）
            if original["predicted_profit"] != 0:
                ratio = actual_profit / original["predicted_profit"]
                timing_score = max(0, min(100, ratio * 100))
            else:
                timing_score = 50 if actual_profit == 0 else 30

            # 综合反馈评分
            feedback_score = (
                direction_correct * 40 +
                profit_correct * 40 +
                timing_score / 100 * 20
            )

            # 更新记录
            c.execute("""
                UPDATE feedback_entries SET
                    actual_direction = ?,
                    actual_profit = ?,
                    direction_correct = ?,
                    profit_correct = ?,
                    timing_score = ?,
                    resolved_at = ?,
                    feedback_score = ?,
                    notes = ?
                WHERE id = ?
            """, (actual_direction, actual_profit, direction_correct, profit_correct,
                  timing_score, now, feedback_score, notes, entry_id))

            conn.commit()

            entry = FeedbackEntry(**{**original,
                "actual_direction": actual_direction,
                "actual_profit": actual_profit,
                "direction_correct": bool(direction_correct),
                "profit_correct": bool(profit_correct),
                "timing_score": timing_score,
                "resolved_at": now,
                "feedback_score": feedback_score,
            })

            # ── 触发反馈处理 ──
            self._process_feedback(entry)

            return entry

    def _process_feedback(self, entry: FeedbackEntry):
        """处理反馈：触发各模块学习和进化"""
        logger.info(f"处理反馈: {entry.signal} {entry.symbol} | "
                    f"预测={entry.predicted_direction} 实际={entry.actual_direction} "
                    f"| 评分={entry.feedback_score:.0f}")

        # 1. 触发回调
        for callback in self._callbacks.get("on_feedback", []):
            try:
                callback(entry)
            except Exception as e:
                logger.warning(f"反馈回调失败: {e}")

        # 2. 成功模式 → 知识库
        if entry.direction_correct and entry.profit_correct:
            self._trigger_knowledge_update(entry)
            for callback in self._callbacks.get("on_pattern_found", []):
                try:
                    callback(entry)
                except Exception as e:
                    logger.warning(f"模式发现回调失败: {e}")

        # 3. 连续失败 → 模型检查
        if entry.feedback_score < 30:
            self._check_model_health(entry.model_id)
            for callback in self._callbacks.get("on_model_degrade", []):
                try:
                    callback(entry)
                except Exception as e:
                    logger.warning(f"模型下滑回调失败: {e}")

        # 4. 滑动窗口统计触发进化
        self._check_evolution_needed(entry.symbol, entry.timeframe)

    def _trigger_knowledge_update(self, entry: FeedbackEntry):
        """将成功模式写入知识库"""
        try:
            from core.analysis.knowledge_base.knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
            kb.add_pattern(
                symbol=entry.symbol,
                timeframe=entry.timeframe,
                signal=entry.signal,
                signal_score=entry.signal_score,
                indicators={"rsi": 50, "macd_hist": 0, "bb_position": 50},
                market={"trend": "UP", "funding_rate": 0, "sentiment": "bullish"},
                result={
                    "entry_price": 0, "exit_price": 0,
                    "profit_pct": entry.actual_profit,
                    "holding_hours": (entry.resolved_at - entry.created_at) / 3600
                },
                description=f"成功信号: {entry.signal} → {entry.actual_profit:+.2f}%",
                key_factors=f"信号={entry.signal} 评分={entry.signal_score:.0f}",
                outcome_verdict="SUCCESS",
            )
            kb.close()
            logger.info(f"成功模式已写入知识库: {entry.id}")
        except Exception as e:
            logger.warning(f"知识库更新失败: {e}")

        self._log_learning_event(
            "pattern_recorded", entry.symbol,
            f"成功模式: {entry.signal} → {entry.actual_profit:+.2f}%",
            {"entry_id": entry.id}
        )

    def _check_model_health(self, model_id: str):
        """检查模型健康状态"""
        if not model_id:
            return

        conn = self._get_conn()
        c = conn.cursor()

        cutoff = int(time.time()) - 86400  # 最近24小时
        c.execute("""
            SELECT AVG(feedback_score) as avg_score, COUNT(*) as total
            FROM feedback_entries
            WHERE model_id = ? AND resolved_at > ?
        """, (model_id, cutoff))

        row = c.fetchone()
        if not row:
            return

        stats = dict(row)
        avg_score = stats["avg_score"] or 50

        # 更新健康状态
        c.execute("""
            INSERT OR REPLACE INTO system_health
            (metric, value, threshold, status, last_updated)
            VALUES (?, ?, ?, ?, ?)
        """, (f"model_{model_id}", avg_score, 50,
              "degraded" if avg_score < 40 else "healthy",
              int(time.time())))

        conn.commit()

        if avg_score < 40:
            self._log_learning_event(
                "model_degraded", model_id,
                f"模型 {model_id} 表现下滑: {avg_score:.0f}",
                {"avg_score": avg_score, "total": stats["total"]}
            )
            logger.warning(f"⚠️ 模型 {model_id} 表现下滑: {avg_score:.0f}")

    def _check_evolution_needed(self, symbol: str, timeframe: str):
        """检查是否需要触发进化"""
        conn = self._get_conn()
        c = conn.cursor()

        cutoff = int(time.time()) - 86400  # 最近24小时
        c.execute("""
            SELECT AVG(feedback_score) as avg_score,
                   SUM(direction_correct) as correct,
                   COUNT(*) as total
            FROM feedback_entries
            WHERE symbol = ? AND timeframe = ? AND resolved_at > ?
        """, (symbol, timeframe, cutoff))

        row = c.fetchone()
        if not row:
            return

        stats = dict(row)
        total = stats["total"] or 0

        if total < 5:
            return  # 数据不足

        accuracy = (stats["correct"] or 0) / total
        avg_score = stats["avg_score"] or 50

        # 连续下滑检测
        c.execute("""
            SELECT AVG(feedback_score) as early_score
            FROM feedback_entries
            WHERE symbol = ? AND timeframe = ?
              AND resolved_at < ? AND resolved_at > ?
        """, (symbol, timeframe, cutoff, cutoff - 86400))

        early_row = c.fetchone()
        early_score = dict(early_row)["early_score"] or 50

        # 触发进化条件
        if avg_score < 50 or (early_score - avg_score > 15 and avg_score < 60):
            for callback in self._callbacks.get("on_evolution_trigger", []):
                try:
                    callback(symbol, timeframe, {
                        "avg_score": avg_score,
                        "accuracy": accuracy,
                        "total": total,
                        "decline": early_score - avg_score,
                    })
                except Exception as e:
                    logger.warning(f"进化触发回调失败: {e}")

            self._log_learning_event(
                "evolution_triggered", symbol,
                f"触发进化: {symbol} {timeframe} | 评分={avg_score:.0f} 准确率={accuracy*100:.0f}%",
                {"avg_score": avg_score, "accuracy": accuracy, "total": total}
            )

    def _log_learning_event(
        self,
        event_type: str,
        symbol: str,
        description: str,
        data: Dict = None,
    ):
        """记录学习事件"""
        import hashlib
        with self._lock:
            conn = self._get_conn()
            c = conn.cursor()

            event_id = hashlib.sha1(
                f"{event_type}{time.time()}".encode()
            ).hexdigest()[:16]

            c.execute("""
                INSERT INTO learning_events
                (id, event_type, symbol, description, data, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (event_id, event_type, symbol, description,
                  json.dumps(data or {}, ensure_ascii=False), int(time.time())))

            conn.commit()

    def get_learning_summary(self, symbol: str = None, days: int = 7) -> Dict:
        """获取学习摘要"""
        conn = self._get_conn()
        c = conn.cursor()

        cutoff = int(time.time()) - days * 86400

        # 总体统计
        c.execute("""
            SELECT
                COUNT(*) as total,
                SUM(direction_correct) as correct,
                AVG(feedback_score) as avg_score,
                AVG(actual_profit) as avg_profit
            FROM feedback_entries
            WHERE resolved_at > ? AND (? IS NULL OR symbol = ?)
        """, (cutoff, symbol, symbol))
        overall = dict(c.fetchone())

        # 按信号统计
        c.execute("""
            SELECT signal,
                   COUNT(*) as count,
                   SUM(direction_correct) as correct,
                   AVG(feedback_score) as avg_score,
                   AVG(actual_profit) as avg_profit
            FROM feedback_entries
            WHERE resolved_at > ? AND (? IS NULL OR symbol = ?)
            GROUP BY signal
        """, (cutoff, symbol, symbol))
        by_signal = [dict(r) for r in c.fetchall()]

        # 学习事件
        c.execute("""
            SELECT * FROM learning_events
            WHERE created_at > ?
            ORDER BY created_at DESC
            LIMIT 20
        """, (cutoff,))
        events = [dict(r) for r in c.fetchall()]

        total = overall["total"] or 0
        correct = overall["correct"] or 0

        return {
            "period_days": days,
            "symbol": symbol or "ALL",
            "total_signals": total,
            "direction_accuracy": round(correct / total * 100, 1) if total > 0 else 0,
            "avg_feedback_score": round(overall["avg_score"] or 0, 1),
            "avg_profit_pct": round(overall["avg_profit"] or 0, 2),
            "by_signal": [
                {**s, "accuracy": round((s["correct"] or 0) / s["count"] * 100, 1)}
                for s in by_signal
            ],
            "learning_events": [
                {**e, "data": json.loads(e["data"]) if e["data"] else {}}
                for e in events[:10]
            ],
        }

    def register_callback(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
            logger.info(f"回调已注册: {event}")

    @safe_execute(default=None)
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
