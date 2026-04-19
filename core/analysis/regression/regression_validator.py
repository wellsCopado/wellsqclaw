"""
回归验证模块 - 预测准确性验证
追踪信号预测 vs 实际结果，对比分析
"""
import sqlite3
import json
import time
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from core.utils.logger import logger
from core.utils.helpers import safe_execute


@dataclass
class Prediction:
    """一次预测记录"""
    id: str
    symbol: str
    timeframe: str
    signal: str          # BUY/SELL/NEUTRAL
    signal_score: float  # -100 to +100
    confidence: float     # 0-100
    predicted_price: float
    prediction_horizon_h: float  # 预测时间跨度(小时)

    # 预测时的市场状态快照
    current_price: float
    rsi: float
    macd_hist: float
    trend: str
    funding_rate: float

    created_at: int


@dataclass
class ValidationResult:
    """验证结果"""
    prediction_id: str
    actual_exit_price: float
    actual_profit_pct: float
    direction_correct: bool
    timing_score: float   # 0-1 时机准确性
    amplitude_score: float  # 0-1 幅度准确性
    overall_accuracy: float  # 0-1 综合准确度

    # 方向是否正确
    direction_match: bool
    # 盈利/亏损
    profitable: bool


class RegressionValidator:
    """
    回归验证 - 追踪预测 vs 实际结果

    四维准确度指标：
    1. 方向正确性 - BUY→涨, SELL→跌
    2. 时机正确性 - 预测时间窗口内是否发生
    3. 幅度准确性 - 预测幅度 vs 实际幅度
    4. 综合评分 - 加权综合
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            import os
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base, "data", "validation.db")
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
            CREATE TABLE IF NOT EXISTS predictions (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                signal TEXT NOT NULL,
                signal_score REAL,
                confidence REAL,
                predicted_price REAL,
                prediction_horizon_h REAL,

                current_price REAL,
                rsi REAL,
                macd_hist REAL,
                trend TEXT,
                funding_rate REAL,

                created_at INTEGER NOT NULL,
                metadata TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS validations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id TEXT UNIQUE,
                actual_exit_price REAL,
                actual_profit_pct REAL,
                direction_correct INTEGER,  -- 0/1
                timing_score REAL,
                amplitude_score REAL,
                overall_accuracy REAL,
                direction_match INTEGER,
                profitable INTEGER,
                validated_at INTEGER,
                FOREIGN KEY (prediction_id) REFERENCES predictions(id)
            )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_pred_symbol ON predictions(symbol)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pred_created ON predictions(created_at DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_val_pred ON validations(prediction_id)")

        conn.commit()
        logger.info(f"回归验证库初始化: {self.db_path}")

    # ── 记录预测 ──
    def record_prediction(self, data: dict) -> str:
        """记录一次预测"""
        import hashlib
        conn = self._get_conn()
        c = conn.cursor()

        pid = data.get('id') or hashlib.md5(
            f"{data.get('symbol')}{data.get('signal')}{data.get('created_at', int(time.time()))}".encode()
        ).hexdigest()[:16]

        c.execute("""
            INSERT OR IGNORE INTO predictions (
                id, symbol, timeframe, signal, signal_score, confidence,
                predicted_price, prediction_horizon_h,
                current_price, rsi, macd_hist, trend, funding_rate,
                created_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid,
            data.get('symbol', 'BTC'),
            data.get('timeframe', '1h'),
            data.get('signal', 'NEUTRAL'),
            data.get('signal_score', 0),
            data.get('confidence', 0),
            data.get('predicted_price', 0),
            data.get('prediction_horizon_h', 24),
            data.get('current_price', 0),
            data.get('rsi', 50),
            data.get('macd_hist', 0),
            data.get('trend', 'SIDEWAYS'),
            data.get('funding_rate', 0),
            data.get('created_at', int(time.time())),
            json.dumps(data.get('metadata', {}), ensure_ascii=False),
        ))

        conn.commit()
        logger.info(f"预测记录: {pid} {data.get('symbol')} {data.get('signal')}")
        return pid

    # ── 验证预测 ──
    def validate_prediction(
        self,
        prediction_id: str,
        exit_price: float,
        exit_time: int = None
    ) -> ValidationResult:
        """验证一个预测的准确性"""
        conn = self._get_conn()
        c = conn.cursor()

        if exit_time is None:
            exit_time = int(time.time())

        c.execute("SELECT * FROM predictions WHERE id = ?", (prediction_id,))
        row = c.fetchone()

        if not row:
            raise ValueError(f"预测不存在: {prediction_id}")

        pred = dict(row)
        entry_price = pred['current_price']
        signal = pred['signal']
        predicted_price = pred['predicted_price'] or entry_price
        horizon_h = pred['prediction_horizon_h']

        # 计算实际盈亏
        if entry_price > 0:
            actual_profit_pct = (exit_price - entry_price) / entry_price * 100
        else:
            actual_profit_pct = 0

        # 方向判断
        if signal == 'BUY':
            direction_match = actual_profit_pct > 0.5  # 涨
        elif signal == 'SELL':
            direction_match = actual_profit_pct < -0.5  # 跌
        else:
            direction_match = abs(actual_profit_pct) < 1.0  # 震荡

        direction_correct = 1 if direction_match else 0

        # 时机准确性
        if horizon_h > 0:
            holding_h = (exit_time - pred['created_at']) / 3600
            timing_score = min(holding_h / horizon_h, 1.0) if horizon_h > 0 else 0.5
        else:
            timing_score = 0.5

        # 幅度准确性
        predicted_move = abs(predicted_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
        actual_move = abs(actual_profit_pct)
        if predicted_move > 0 and actual_move > 0:
            amplitude_score = min(actual_move / predicted_move, 1.0) if signal == 'BUY' else min(predicted_move / actual_move, 1.0)
        else:
            amplitude_score = 0.5

        # 综合准确度
        overall = (direction_correct + timing_score + amplitude_score) / 3

        result = ValidationResult(
            prediction_id=prediction_id,
            actual_exit_price=exit_price,
            actual_profit_pct=round(actual_profit_pct, 3),
            direction_correct=direction_correct == 1,
            timing_score=round(timing_score, 3),
            amplitude_score=round(amplitude_score, 3),
            overall_accuracy=round(overall, 3),
            direction_match=direction_match,
            profitable=actual_profit_pct > 0,
        )

        # 存储验证结果
        c.execute("""
            INSERT OR REPLACE INTO validations (
                prediction_id, actual_exit_price, actual_profit_pct,
                direction_correct, timing_score, amplitude_score,
                overall_accuracy, direction_match, profitable, validated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prediction_id, exit_price, result.actual_profit_pct,
            direction_correct, result.timing_score, result.amplitude_score,
            result.overall_accuracy, 1 if direction_match else 0,
            1 if result.profitable else 0, exit_time,
        ))

        conn.commit()
        logger.info(
            f"验证完成: {prediction_id} | "
            f"信号={signal} 实际={actual_profit_pct:+.2f}% | "
            f"方向={'✅' if direction_match else '❌'} | "
            f"综合={overall:.1%}"
        )

        return result

    # ── 统计报告 ──
    def get_accuracy_report(self, symbol: str = None, days: int = 30) -> dict:
        """获取准确度报告"""
        conn = self._get_conn()
        c = conn.cursor()

        cutoff = int(time.time()) - days * 86400
        symbol_filter = f"AND p.symbol = '{symbol}'" if symbol else ""

        c.execute(f"""
            SELECT
                COUNT(*) as total_predictions,
                SUM(CASE WHEN v.direction_correct = 1 THEN 1 ELSE 0 END) as direction_correct_count,
                SUM(CASE WHEN v.profitable = 1 THEN 1 ELSE 0 END) as profitable_count,
                AVG(v.overall_accuracy) as avg_accuracy,
                AVG(v.timing_score) as avg_timing,
                AVG(v.amplitude_score) as avg_amplitude,
                AVG(v.actual_profit_pct) as avg_profit,
                AVG(p.confidence) as avg_confidence
            FROM predictions p
            LEFT JOIN validations v ON p.id = v.prediction_id
            WHERE p.created_at > ? {symbol_filter}
        """, (cutoff,))

        row = c.fetchone()
        if not row or row['total_predictions'] == 0:
            return {
                "total_predictions": 0,
                "direction_accuracy": 0,
                "win_rate": 0,
                "avg_accuracy": 0,
                "avg_timing": 0,
                "avg_amplitude": 0,
                "avg_profit_pct": 0,
                "avg_confidence": 0,
                "trend": "数据不足",
            }

        total = row['total_predictions']
        direction_correct = row['direction_correct_count'] or 0
        profitable = row['profitable_count'] or 0
        avg_acc = row['avg_accuracy'] or 0
        avg_timing = row['avg_timing'] or 0
        avg_amplitude = row['avg_amplitude'] or 0
        avg_profit = row['avg_profit'] or 0
        avg_conf = row['avg_confidence'] or 0

        # 判断趋势
        if avg_acc >= 0.7:
            trend = "📈 持续改善"
        elif avg_acc >= 0.5:
            trend = "➡️ 基本稳定"
        elif avg_acc >= 0.3:
            trend = "⚠️ 需要优化"
        else:
            trend = "🔴 严重偏差"

        return {
            "total_predictions": total,
            "validated": int(direction_correct + (total - direction_correct)),  # 有验证结果数
            "direction_accuracy": round(direction_correct / total * 100, 1) if total > 0 else 0,
            "win_rate": round(profitable / total * 100, 1) if total > 0 else 0,
            "avg_accuracy": round(avg_acc * 100, 1),
            "avg_timing": round(avg_timing * 100, 1),
            "avg_amplitude": round(avg_amplitude * 100, 1),
            "avg_profit_pct": round(avg_profit, 2),
            "avg_confidence": round(avg_conf, 1),
            "trend": trend,
            "period_days": days,
        }

    def get_signal_accuracy(self, signal_type: str, symbol: str = None) -> dict:
        """获取特定信号类型的准确率"""
        conn = self._get_conn()
        c = conn.cursor()

        sym = f"AND p.symbol = '{symbol}'" if symbol else ""

        c.execute(f"""
            SELECT COUNT(*) total,
                   SUM(CASE WHEN v.direction_correct = 1 THEN 1 ELSE 0 END) correct,
                   AVG(v.overall_accuracy) avg_acc
            FROM predictions p
            JOIN validations v ON p.id = v.prediction_id
            WHERE p.signal = ? {sym}
        """, (signal_type,))

        row = c.fetchone()
        if not row or row['total'] == 0:
            return {"signal": signal_type, "total": 0, "accuracy": 0}

        return {
            "signal": signal_type,
            "total": row['total'],
            "direction_accuracy": round(row['correct'] / row['total'] * 100, 1) if row['total'] > 0 else 0,
            "avg_accuracy": round((row['avg_acc'] or 0) * 100, 1),
        }

    def get_recent_validations(self, limit: int = 10) -> list[dict]:
        """获取最近的验证结果"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT p.symbol, p.signal, p.signal_score, p.confidence,
                   v.actual_profit_pct, v.direction_correct, v.overall_accuracy, v.profitable,
                   v.validated_at
            FROM predictions p
            JOIN validations v ON p.id = v.prediction_id
            ORDER BY v.validated_at DESC
            LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        return [
            {
                "symbol": r['symbol'],
                "signal": r['signal'],
                "score": r['signal_score'],
                "profit_pct": round(r['actual_profit_pct'], 2),
                "correct": bool(r['direction_correct']),
                "accuracy": round(r['overall_accuracy'] * 100, 1),
                "profitable": bool(r['profitable']),
                "time": datetime.fromtimestamp(r['validated_at']).strftime("%m-%d %H:%M"),
            }
            for r in rows
        ]

    @safe_execute(default=None)
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


_validator: Optional[RegressionValidator] = None


def get_validator() -> RegressionValidator:
    global _validator
    if _validator is None:
        _validator = RegressionValidator()
    return _validator
