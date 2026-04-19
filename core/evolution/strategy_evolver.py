"""
策略进化器 (Strategy Evolver)
根据归因分析结果，动态调整交易策略参数
自动发现最优策略组合
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
class StrategyParams:
    """策略参数"""
    id: str
    name: str
    symbol: str
    timeframe: str

    # 信号权重
    w_funding: float = 0.25   # 资金费率权重
    w_oi: float = 0.20       # 持仓量权重
    w_ls: float = 0.25        # 多空比权重
    w_liq: float = 0.15       # 爆仓权重
    w_momentum: float = 0.15  # 动量权重

    # 阈值设置
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    funding_threshold: float = 0.001  # 极端费率阈值
    liq_threshold: float = 50_000_000.0  # 爆仓阈值 $50M

    # 风控
    max_position_pct: float = 0.10   # 最大仓位 10%
    stop_loss_pct: float = 0.02       # 止损 2%
    take_profit_pct: float = 0.04     # 止盈 4%

    # 状态
    version: int = 1
    created_at: int = 0
    is_active: bool = True
    total_trades: int = 0
    win_rate: float = 0.0


class StrategyEvolver:
    """
    策略进化器
    1. 追踪策略表现
    2. 根据归因结果调整参数
    3. A/B测试新策略
    4. 自动发现最优参数组合
    """

    # 预设策略
    PRESETS = {
        "conservative": {
            "name": "保守策略",
            "w_funding": 0.30, "w_oi": 0.15, "w_ls": 0.20, "w_liq": 0.15, "w_momentum": 0.20,
            "rsi_oversold": 25, "rsi_overbought": 75,
            "funding_threshold": 0.002, "liq_threshold": 100_000_000,
            "max_position_pct": 0.05, "stop_loss_pct": 0.015, "take_profit_pct": 0.03,
        },
        "aggressive": {
            "name": "激进策略",
            "w_funding": 0.20, "w_oi": 0.25, "w_ls": 0.20, "w_liq": 0.20, "w_momentum": 0.15,
            "rsi_oversold": 35, "rsi_overbought": 65,
            "funding_threshold": 0.0005, "liq_threshold": 20_000_000,
            "max_position_pct": 0.20, "stop_loss_pct": 0.03, "take_profit_pct": 0.06,
        },
        "balanced": {
            "name": "均衡策略",
            "w_funding": 0.25, "w_oi": 0.20, "w_ls": 0.25, "w_liq": 0.15, "w_momentum": 0.15,
            "rsi_oversold": 30, "rsi_overbought": 70,
            "funding_threshold": 0.001, "liq_threshold": 50_000_000,
            "max_position_pct": 0.10, "stop_loss_pct": 0.02, "take_profit_pct": 0.04,
        },
    }

    def __init__(self, db_path: str = None):
        if db_path is None:
            import os
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base, "data", "strategy_evolver.db")
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
            CREATE TABLE IF NOT EXISTS strategies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                params TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                created_at INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                total_trades INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                avg_profit REAL DEFAULT 0.0,
                max_drawdown REAL DEFAULT 0.0
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS strategy_trades (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                signal TEXT NOT NULL,
                entry_price REAL,
                exit_price REAL,
                profit_pct REAL,
                outcome TEXT,
                attribution TEXT,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(strategy_id) REFERENCES strategies(id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS evolution_history (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                from_version INTEGER,
                to_version INTEGER,
                changes TEXT,
                reason TEXT,
                result_pct REAL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(strategy_id) REFERENCES strategies(id)
            )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_strat_symbol ON strategies(symbol)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_trades_strat ON strategy_trades(strategy_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_evo_strat ON evolution_history(strategy_id)")

        conn.commit()

        # 插入预设策略
        self._insert_preset_strategies()
        logger.info(f"策略进化器初始化: {self.db_path}")

    def _insert_preset_strategies(self):
        conn = self._get_conn()
        c = conn.cursor()

        for symbol in ["BTC", "ETH"]:
            for tf in ["1h", "4h", "1d"]:
                for preset_name, preset in self.PRESETS.items():
                    c.execute("""
                        SELECT id FROM strategies
                        WHERE symbol = ? AND timeframe = ? AND name = ?
                    """, (symbol, tf, preset["name"]))
                    if not c.fetchone():
                        strategy_id = hashlib.sha1(
                            f"{symbol}{tf}{preset_name}{time.time()}".encode()
                        ).hexdigest()[:16]
                        c.execute("""
                            INSERT INTO strategies
                            (id, name, symbol, timeframe, params, version, created_at)
                            VALUES (?, ?, ?, ?, ?, 1, ?)
                        """, (strategy_id, preset["name"], symbol, tf,
                              json.dumps(preset), int(time.time())))

        conn.commit()

    def get_strategy(self, symbol: str, timeframe: str) -> Dict:
        """获取最优策略"""
        conn = self._get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT * FROM strategies
            WHERE symbol = ? AND timeframe = ? AND is_active = 1
            ORDER BY win_rate DESC, total_trades DESC
            LIMIT 1
        """, (symbol, timeframe))
        row = c.fetchone()

        if not row:
            # 返回默认均衡策略
            row = dict(c.execute("""
                SELECT * FROM strategies WHERE name = '均衡策略' LIMIT 1
            """).fetchone() or {})

        if not row:
            return {}

        d = dict(row)
        params = json.loads(d["params"])

        return {
            "id": d["id"],
            "name": d["name"],
            "symbol": d["symbol"],
            "timeframe": d["timeframe"],
            "version": d["version"],
            "params": params,
            "stats": {
                "total_trades": d["total_trades"],
                "win_rate": round(d["win_rate"] * 100, 1),
                "avg_profit": round(d["avg_profit"], 2),
                "max_drawdown": round(d["max_drawdown"], 2),
            }
        }

    def record_trade(
        self,
        strategy_id: str,
        symbol: str,
        signal: str,
        entry_price: float,
        exit_price: float,
        profit_pct: float,
        outcome: str,
        attribution: Dict = None,
    ) -> str:
        """记录一笔交易"""
        conn = self._get_conn()
        c = conn.cursor()

        trade_id = hashlib.sha1(
            f"{strategy_id}{time.time()}".encode()
        ).hexdigest()[:16]
        now = int(time.time())

        c.execute("""
            INSERT INTO strategy_trades
            (id, strategy_id, symbol, signal, entry_price, exit_price, profit_pct, outcome, attribution, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (trade_id, strategy_id, symbol, signal, entry_price, exit_price, profit_pct, outcome,
              json.dumps(attribution or {}), now))

        # 更新策略统计
        c.execute("""
            UPDATE strategies SET
                total_trades = total_trades + 1,
                win_rate = (
                    SELECT SUM(CASE WHEN profit_pct > 0 THEN 1.0 ELSE 0.0 END) / COUNT(*)
                    FROM strategy_trades WHERE strategy_id = ?
                ),
                avg_profit = (
                    SELECT AVG(profit_pct) FROM strategy_trades WHERE strategy_id = ?
                )
            WHERE id = ?
        """, (strategy_id, strategy_id, strategy_id))

        conn.commit()
        return trade_id

    def evolve_strategy(
        self,
        strategy_id: str,
        attribution_result: Dict,
    ) -> Tuple[str, Dict]:
        """
        根据归因分析结果进化策略
        返回: (evolution_id, new_params)
        """
        conn = self._get_conn()
        c = conn.cursor()

        # 获取当前策略
        c.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,))
        row = c.fetchone()
        if not row:
            return "", {}

        current = dict(row)
        current_params = json.loads(current["params"])
        new_params = current_params.copy()

        changes = []

        # ── 分析归因结果，调整权重 ──
        factors = attribution_result.get("factors", {})
        technical = factors.get("technical", {})
        fundamental = factors.get("fundamental", {})
        sentiment = factors.get("sentiment", {})
        execution = factors.get("execution", {})

        # 调整信号权重
        if technical.get("score", 50) < 40:
            # 技术面弱，降低动量权重，提高资金费率权重
            new_params["w_momentum"] = max(0.05, new_params["w_momentum"] - 0.05)
            new_params["w_funding"] = min(0.40, new_params["w_funding"] + 0.05)
            changes.append("技术面弱: 动量权重↓ 资金费率↑")

        if sentiment.get("score", 50) < 40:
            # 情绪面弱，降低多空比权重
            new_params["w_ls"] = max(0.10, new_params["w_ls"] - 0.05)
            new_params["w_oi"] = min(0.30, new_params["w_oi"] + 0.05)
            changes.append("情绪面弱: 多空比权重↓ 持仓量↑")

        # 调整止损止盈
        if attribution_result.get("risk_factor") == "HIGH":
            # 高风险，降低止损扩大
            new_params["stop_loss_pct"] = min(0.05, new_params["stop_loss_pct"] * 1.5)
            new_params["take_profit_pct"] = min(0.08, new_params["take_profit_pct"] * 1.3)
            new_params["max_position_pct"] = max(0.03, new_params["max_position_pct"] * 0.7)
            changes.append("高风险: 扩大止损+止盈，降低仓位")

        # RSI 阈值优化
        recent_rsis = attribution_result.get("recent_rsis", [])
        if recent_rsis:
            avg_rsi = sum(recent_rsis) / len(recent_rsis)
            if avg_rsi > 65:
                new_params["rsi_overbought"] = min(80, new_params["rsi_overbought"] + 5)
                changes.append(f"RSI持续偏高: 超买阈值调至{new_params['rsi_overbought']}")

        # 资金费率阈值
        if fundamental.get("funding_extreme", False):
            new_params["funding_threshold"] *= 1.5
            changes.append("资金费率极端: 阈值放宽")

        # 爆仓阈值
        if sentiment.get("liquidation_spike", False):
            new_params["liq_threshold"] *= 1.3
            changes.append("爆仓激增: 阈值扩大")

        # 版本号+1
        new_version = current["version"] + 1

        # 计算改进幅度
        new_win_rate = current.get("win_rate", 0.5)
        changes_str = "\n".join(changes) if changes else "参数微调"

        # 保存历史
        evo_id = hashlib.sha1(
            f"{strategy_id}{new_version}{time.time()}".encode()
        ).hexdigest()[:16]

        c.execute("""
            INSERT INTO evolution_history
            (id, strategy_id, from_version, to_version, changes, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (evo_id, strategy_id, current["version"], new_version, changes_str,
              attribution_result.get("summary", ""), int(time.time())))

        # 创建新版本策略
        new_id = hashlib.sha1(
            f"{strategy_id}v{new_version}{time.time()}".encode()
        ).hexdigest()[:16]

        c.execute("""
            INSERT INTO strategies
            (id, name, symbol, timeframe, params, version, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (new_id, current["name"], current["symbol"], current["timeframe"],
              json.dumps(new_params), new_version, int(time.time())))

        # 旧版本设为非活跃
        c.execute("UPDATE strategies SET is_active = 0 WHERE id = ?", (strategy_id,))

        conn.commit()

        logger.info(f"策略进化: {strategy_id} v{current['version']}→v{new_version}")
        for ch in changes:
            logger.info(f"  调整: {ch}")

        return evo_id, new_params

    def get_evolution_history(
        self, strategy_id: str = None, limit: int = 20
    ) -> List[Dict]:
        """获取进化历史"""
        conn = self._get_conn()
        c = conn.cursor()

        if strategy_id:
            c.execute("""
                SELECT * FROM evolution_history
                WHERE strategy_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (strategy_id, limit))
        else:
            c.execute("""
                SELECT eh.*, s.name as strategy_name, s.symbol
                FROM evolution_history eh
                JOIN strategies s ON eh.strategy_id = s.id
                ORDER BY eh.created_at DESC
                LIMIT ?
            """, (limit,))

        return [dict(r) for r in c.fetchall()]

    def backtest_params(
        self,
        strategy_id: str,
        test_params: Dict,
        lookback_days: int = 30,
    ) -> Dict:
        """
        回测新参数
        用历史数据测试新参数组合的表现
        """
        conn = self._get_conn()
        c = conn.cursor()

        # 获取历史交易
        cutoff = int(time.time()) - lookback_days * 86400
        c.execute("""
            SELECT * FROM strategy_trades
            WHERE strategy_id = ? AND created_at > ?
            ORDER BY created_at
        """, (strategy_id, cutoff))
        trades = [dict(r) for r in c.fetchall()]

        if len(trades) < 3:
            return {"error": "历史数据不足", "available_trades": len(trades)}

        # 模拟新参数下的表现
        wins = 0
        losses = 0
        total_profit = 0.0
        max_drawdown = 0.0
        peak = 0.0

        for trade in trades:
            # 新参数下是否触发交易
            profit = trade["profit_pct"]

            # 调整止损止盈后的结果
            sl = test_params.get("stop_loss_pct", 0.02)
            tp = test_params.get("take_profit_pct", 0.04)

            if profit > 0:
                # 实际利润但受止盈限制
                adjusted = min(profit, tp * 1.5)  # 止盈最多1.5倍
                wins += 1
            else:
                # 亏损但受止损限制
                adjusted = max(profit, -sl * 1.5)  # 止损最多1.5倍
                losses += 1

            total_profit += adjusted
            peak = max(peak, peak + adjusted)
            drawdown = peak - (peak + adjusted)
            max_drawdown = min(max_drawdown, drawdown)

        total = wins + losses
        win_rate = wins / total if total > 0 else 0

        return {
            "strategy_id": strategy_id,
            "trades_tested": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate * 100, 1),
            "total_profit_pct": round(total_profit * 100, 2),
            "max_drawdown_pct": round(abs(max_drawdown) * 100, 2),
            "recommendation": "APPLY" if win_rate > 0.55 else "KEEP_CURRENT",
        }

    def get_all_strategies(self, symbol: str = None) -> List[Dict]:
        """获取所有策略"""
        conn = self._get_conn()
        c = conn.cursor()

        if symbol:
            c.execute("""
                SELECT * FROM strategies
                WHERE symbol = ?
                ORDER BY is_active DESC, win_rate DESC
            """, (symbol,))
        else:
            c.execute("""
                SELECT * FROM strategies
                ORDER BY is_active DESC, win_rate DESC
                LIMIT 50
            """)

        results = []
        for row in c.fetchall():
            d = dict(row)
            results.append({
                "id": d["id"],
                "name": d["name"],
                "symbol": d["symbol"],
                "timeframe": d["timeframe"],
                "version": d["version"],
                "is_active": bool(d["is_active"]),
                "params": json.loads(d["params"]),
                "stats": {
                    "total_trades": d["total_trades"],
                    "win_rate": round(d["win_rate"] * 100, 1),
                    "avg_profit": round(d["avg_profit"], 2),
                }
            })
        return results

    @safe_execute(default=None)
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
