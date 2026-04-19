"""
CryptoMind Pro Plus AI - Paper Trading 模拟交易引擎

⚠️ DISCLAIMER: 本模块仅供模拟交易，不构成任何投资建议。
Paper trading does NOT guarantee real-market results.

功能:
- 模拟账户管理（初始资金/余额/持仓）
- 模拟下单（限价/市价，含滑点模拟）
- 手续费计算（Maker/Taker费率）
- 持仓盈亏实时追踪
- 交易历史与绩效统计
- 信号冷却期（防止过度交易）
"""

import json
import os
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

from core.utils.logger import logger
from core.utils.helpers import safe_execute


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"


@dataclass
class Position:
    symbol: str
    side: str  # long / short
    entry_price: float
    quantity: float
    leverage: int = 1
    open_time: int = 0
    unrealized_pnl: float = 0.0
    liquidation_price: float = 0.0

    def to_dict(self):
        return asdict(self)


@dataclass
class Order:
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float]
    status: str = "pending"
    filled_price: float = 0.0
    filled_time: int = 0
    fee: float = 0.0
    slippage: float = 0.0
    created_time: int = 0

    def to_dict(self):
        return asdict(self)


@dataclass
class TradeRecord:
    trade_id: str
    order_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    fee: float
    slippage: float
    hold_time_sec: int
    close_time: int

    def to_dict(self):
        return asdict(self)


# ─────────────────────────────────────────────
# 信号冷却期
# ─────────────────────────────────────────────
class SignalCooldown:
    """防止同一币种短时间内重复开仓"""

    def __init__(self, default_cooldown_sec: int = 300):
        self._last_signal: dict[str, int] = {}  # symbol -> timestamp
        self._cooldown = default_cooldown_sec

    def can_trade(self, symbol: str) -> tuple[bool, int]:
        """返回 (是否允许, 剩余冷却秒数)"""
        now = int(time.time())
        last = self._last_signal.get(symbol, 0)
        remaining = max(0, self._cooldown - (now - last))
        return remaining == 0, remaining

    def record_trade(self, symbol: str):
        self._last_signal[symbol] = int(time.time())

    def set_cooldown(self, seconds: int):
        self._cooldown = max(30, seconds)  # 最低30秒


# ─────────────────────────────────────────────
# Paper Trading Engine
# ─────────────────────────────────────────────
class PaperTradingEngine:
    """
    模拟交易引擎

    配置:
    - initial_balance: 初始资金 (USDT)
    - maker_fee: Maker费率 (默认0.02%)
    - taker_fee: Taker费率 (默认0.05%)
    - slippage_bps: 滑点基点 (默认5bps = 0.05%)
    - cooldown_sec: 信号冷却期 (默认300秒=5分钟)
    - max_position_pct: 单仓最大占总资金比例 (默认20%)
    - max_drawdown_pct: 最大回撤止损线 (默认15%)
    """

    DEFAULT_CONFIG = {
        "initial_balance": 10000.0,
        "maker_fee": 0.0002,       # 0.02%
        "taker_fee": 0.0005,       # 0.05%
        "slippage_bps": 5,          # 5 bps = 0.05%
        "cooldown_sec": 300,        # 5分钟
        "max_position_pct": 0.20,   # 20%
        "max_drawdown_pct": 0.15,   # 15%
    }

    def __init__(self, db_path: str = None, config: dict = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "data", "paper_trading.db"
            )
        self._db_path = db_path
        self._config = {**self.DEFAULT_CONFIG, **(config or {})}

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

        self._cooldown = SignalCooldown(self._config["cooldown_sec"])
        self._positions: dict[str, Position] = {}
        self._load_state()

        logger.info(f"📊 Paper Trading引擎初始化: 余额=${self.balance:,.2f}")

    def _init_db(self):
        c = self._conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                balance REAL NOT NULL DEFAULT 10000,
                equity REAL NOT NULL DEFAULT 10000,
                initial_balance REAL NOT NULL,
                total_pnl REAL NOT NULL DEFAULT 0,
                total_trades INTEGER NOT NULL DEFAULT 0,
                win_trades INTEGER NOT NULL DEFAULT 0,
                loss_trades INTEGER NOT NULL DEFAULT 0,
                total_fee REAL NOT NULL DEFAULT 0,
                max_equity REAL NOT NULL DEFAULT 10000,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL,
                status TEXT NOT NULL DEFAULT 'pending',
                filled_price REAL NOT NULL DEFAULT 0,
                filled_time INTEGER NOT NULL DEFAULT 0,
                fee REAL NOT NULL DEFAULT 0,
                slippage REAL NOT NULL DEFAULT 0,
                created_time INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                quantity REAL NOT NULL,
                pnl REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                fee REAL NOT NULL DEFAULT 0,
                slippage REAL NOT NULL DEFAULT 0,
                hold_time_sec INTEGER NOT NULL DEFAULT 0,
                close_time INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                action TEXT NOT NULL,
                detail TEXT
            );
        """)
        self._conn.commit()

        # 确保有账户
        c.execute("SELECT COUNT(*) FROM accounts")
        if c.fetchone()[0] == 0:
            now = int(time.time())
            init_bal = self._config["initial_balance"]
            c.execute(
                "INSERT INTO accounts (id, balance, equity, initial_balance, max_equity, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("default", init_bal, init_bal, init_bal, init_bal, now),
            )
            self._conn.commit()

    def _load_state(self):
        c = self._conn.cursor()
        c.execute("SELECT * FROM accounts WHERE id = 'default'")
        row = c.fetchone()
        self.balance = row["balance"]
        self.equity = row["equity"]
        self.initial_balance = row["initial_balance"]
        self.total_pnl = row["total_pnl"]
        self.total_trades = row["total_trades"]
        self.win_trades = row["win_trades"]
        self.loss_trades = row["loss_trades"]
        self.total_fee = row["total_fee"]
        self.max_equity = row["max_equity"]

    def _save_state(self):
        now = int(time.time())
        c = self._conn.cursor()
        c.execute(
            """UPDATE accounts SET
                balance=?, equity=?, total_pnl=?, total_trades=?,
                win_trades=?, loss_trades=?, total_fee=?, max_equity=?, updated_at=?
            WHERE id='default'""",
            (self.balance, self.equity, self.total_pnl, self.total_trades,
             self.win_trades, self.loss_trades, self.total_fee, self.max_equity, now),
        )
        self._conn.commit()

    def _audit(self, action: str, detail: str = ""):
        c = self._conn.cursor()
        c.execute(
            "INSERT INTO audit_log (ts, action, detail) VALUES (?, ?, ?)",
            (int(time.time()), action, detail),
        )
        self._conn.commit()

    # ─── 下单 ───

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float = None,
        order_type: str = "market",
        current_price: float = None,
    ) -> dict:
        """
        模拟下单

        Args:
            symbol: 交易对 e.g. BTC/USDT
            side: buy / sell
            quantity: 数量
            price: 限价单价格 (None=市价)
            order_type: market / limit
            current_price: 当前市价 (用于滑点计算)
        Returns:
            订单结果 dict
        """
        try:
            # 1. 冷却期检查
            can, remaining = self._cooldown.can_trade(symbol)
            if not can:
                return {
                    "success": False,
                    "error": f"Signal cooldown: {remaining}s remaining for {symbol}",
                    "cooldown_remaining": remaining,
                }

            # 2. 最大回撤检查
            drawdown = (self.max_equity - self.equity) / self.max_equity if self.max_equity > 0 else 0
            if drawdown >= self._config["max_drawdown_pct"]:
                self._audit("ORDER_REJECTED_DRAWDOWN", f"drawdown={drawdown:.2%}")
                return {
                    "success": False,
                    "error": f"Max drawdown reached ({drawdown:.1%}). Trading halted.",
                    "drawdown": drawdown,
                }

            # 3. 计算成交价格（含滑点）
            if current_price is None:
                current_price = price or 0
            if current_price <= 0:
                return {"success": False, "error": "No valid price provided"}

            slippage_pct = self._config["slippage_bps"] / 10000.0
            if side == "buy":
                fill_price = current_price * (1 + slippage_pct)
            else:
                fill_price = current_price * (1 - slippage_pct)

            actual_slippage = abs(fill_price - current_price)

            # 4. 手续费计算
            fee_rate = self._config["taker_fee"]
            fee = fill_price * quantity * fee_rate

            # 5. 仓位大小检查
            notional = fill_price * quantity
            max_notional = self.equity * self._config["max_position_pct"]
            if notional > max_notional:
                quantity = max_notional / fill_price
                notional = fill_price * quantity
                fee = notional * fee_rate
                logger.warning(f"\u26a0\ufe0f Position auto-sized to {quantity:.6f} {symbol} (max {self._config['max_position_pct']:.0%})")

            # 6. 余额检查 (买入)
            if side == "buy":
                cost = notional + fee
                if cost > self.balance:
                    quantity = self.balance / (fill_price * (1 + fee_rate))
                    notional = fill_price * quantity
                    fee = notional * fee_rate
                    if quantity <= 0:
                        return {"success": False, "error": "Insufficient balance"}

            # 7. 执行
            order_id = f"P{int(time.time()*1000)}"
            now = int(time.time())

            if side == "buy":
                self.balance -= (notional + fee)
                pos = Position(
                    symbol=symbol,
                    side="long",
                    entry_price=fill_price,
                    quantity=quantity,
                    open_time=now,
                )
                self._positions[symbol] = pos
            elif side == "sell":
                if symbol in self._positions:
                    pos = self._positions.pop(symbol)
                    pnl = (fill_price - pos.entry_price) * quantity
                    pnl_pct = (fill_price - pos.entry_price) / pos.entry_price * 100
                    hold_time = now - pos.open_time
                    self.balance += (notional - fee)

                    trade = TradeRecord(
                        trade_id=f"T{now}",
                        order_id=order_id,
                        symbol=symbol,
                        side="long",
                        entry_price=pos.entry_price,
                        exit_price=fill_price,
                        quantity=quantity,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        fee=fee,
                        slippage=actual_slippage,
                        hold_time_sec=hold_time,
                        close_time=now,
                    )
                    self._record_trade(trade)
                else:
                    return {"success": False, "error": f"No open position for {symbol}"}

            order = Order(
                order_id=order_id, symbol=symbol, side=side, order_type=order_type,
                quantity=quantity, price=price, status="filled",
                filled_price=fill_price, filled_time=now, fee=fee,
                slippage=actual_slippage, created_time=now,
            )
            self._record_order(order)
            self._cooldown.record_trade(symbol)
            self._update_equity()
            self._save_state()
            self._audit("ORDER_FILLED", f"{side} {quantity:.6f} {symbol} @ ${fill_price:.2f} fee=${fee:.4f}")

            logger.info(f"\U0001f4ca Paper Trade: {side.upper()} {quantity:.6f} {symbol} @ ${fill_price:.2f} fee=${fee:.4f} slippage=${actual_slippage:.2f}")

            return {
                "success": True,
                "order_id": order_id,
                "side": side,
                "symbol": symbol,
                "quantity": quantity,
                "fill_price": fill_price,
                "fee": fee,
                "slippage": actual_slippage,
                "balance": self.balance,
                "equity": self.equity,
            }
        except Exception as e:
            logger.error(f"模拟下单失败: {e}")
            return {"success": False, "error": str(e)}

    def close_position(self, symbol: str, current_price: float) -> dict:
        """平仓"""
        if symbol not in self._positions:
            return {"success": False, "error": f"No position for {symbol}"}
        return self.place_order(symbol, "sell", self._positions[symbol].quantity, current_price=current_price)

    def update_market_price(self, symbol: str, price: float):
        """更新持仓的未实现盈亏"""
        if symbol in self._positions:
            pos = self._positions[symbol]
            pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity
            pos.liquidation_price = pos.entry_price * (1 - 1 / pos.leverage * 0.9)
            self._update_equity()
            self._save_state()

    def _update_equity(self):
        """更新权益 = 余额 + 未实现盈亏"""
        unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        self.equity = self.balance + unrealized
        self.total_pnl = self.equity - self.initial_balance
        if self.equity > self.max_equity:
            self.max_equity = self.equity

    def _record_order(self, order: Order):
        c = self._conn.cursor()
        d = order.to_dict()
        cols = list(d.keys())
        vals = list(d.values())
        c.execute(
            f"INSERT OR REPLACE INTO orders ({','.join(cols)}) VALUES ({','.join(['?'] * len(cols))})",
            vals,
        )
        self._conn.commit()

    def _record_trade(self, trade: TradeRecord):
        c = self._conn.cursor()
        d = trade.to_dict()
        cols = list(d.keys())
        vals = list(d.values())
        c.execute(
            f"INSERT OR REPLACE INTO trades ({','.join(cols)}) VALUES ({','.join(['?'] * len(cols))})",
            vals,
        )
        self.total_trades += 1
        if trade.pnl >= 0:
            self.win_trades += 1
        else:
            self.loss_trades += 1
        self.total_fee += trade.fee
        self._conn.commit()

    # ─── 查询 ───

    def get_account(self) -> dict:
        return {
            "balance": round(self.balance, 2),
            "equity": round(self.equity, 2),
            "initial_balance": self.initial_balance,
            "total_pnl": round(self.total_pnl, 2),
            "total_pnl_pct": round(self.total_pnl / self.initial_balance * 100, 2) if self.initial_balance else 0,
            "total_trades": self.total_trades,
            "win_trades": self.win_trades,
            "loss_trades": self.loss_trades,
            "win_rate": round(self.win_trades / self.total_trades * 100, 1) if self.total_trades else 0,
            "total_fee": round(self.total_fee, 4),
            "max_drawdown": round((self.max_equity - self.equity) / self.max_equity * 100, 2) if self.max_equity else 0,
            "open_positions": len(self._positions),
        }

    def get_positions(self) -> list[dict]:
        return [p.to_dict() for p in self._positions.values()]

    def get_trade_history(self, limit: int = 50) -> list[dict]:
        c = self._conn.cursor()
        c.execute("SELECT * FROM trades ORDER BY close_time DESC LIMIT ?", (limit,))
        return [dict(row) for row in c.fetchall()]

    def get_order_history(self, limit: int = 50) -> list[dict]:
        c = self._conn.cursor()
        c.execute("SELECT * FROM orders ORDER BY created_time DESC LIMIT ?", (limit,))
        return [dict(row) for row in c.fetchall()]

    def get_performance(self) -> dict:
        """绩效分析"""
        try:
            c = self._conn.cursor()
            c.execute("SELECT * FROM trades ORDER BY close_time DESC")
            trades = c.fetchall()

            if not trades:
                return {"message": "No trades yet"}

            pnls = [t["pnl"] for t in trades]
            win_pnls = [p for p in pnls if p >= 0]
            loss_pnls = [p for p in pnls if p < 0]

            max_consecutive_loss = 0
            current_streak = 0
            for p in pnls:
                if p < 0:
                    current_streak += 1
                    max_consecutive_loss = max(max_consecutive_loss, current_streak)
                else:
                    current_streak = 0

            avg_pnl = sum(pnls) / len(pnls) if pnls else 0
            pnl_std = (sum((p - avg_pnl) ** 2 for p in pnls) / len(pnls)) ** 0.5 if len(pnls) > 1 else 1
            sharpe = avg_pnl / pnl_std if pnl_std > 0 else 0

            avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
            avg_loss = abs(sum(loss_pnls) / len(loss_pnls)) if loss_pnls else 1
            profit_factor = avg_win / avg_loss if avg_loss > 0 else float("inf")

            return {
                "total_trades": len(trades),
                "win_rate": round(len(win_pnls) / len(pnls) * 100, 1),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(-abs(avg_loss), 2) if loss_pnls else 0,
                "profit_factor": round(profit_factor, 2),
                "max_consecutive_loss": max_consecutive_loss,
                "sharpe_approx": round(sharpe, 2),
                "total_pnl": round(sum(pnls), 2),
                "total_fee": round(sum(t["fee"] for t in trades), 4),
                "total_slippage": round(sum(t["slippage"] for t in trades), 4),
            }
        except Exception as e:
            logger.error(f"绩效分析失败: {e}")
            return {"error": str(e)}

    @safe_execute(default=None)
    def reset(self, new_balance: float = None):
        """重置模拟账户"""
        bal = new_balance or self._config["initial_balance"]
        self.balance = bal
        self.equity = bal
        self.initial_balance = bal
        self.total_pnl = 0
        self.total_trades = 0
        self.win_trades = 0
        self.loss_trades = 0
        self.total_fee = 0
        self.max_equity = bal
        self._positions.clear()
        self._save_state()
        self._audit("ACCOUNT_RESET", f"balance={bal}")
        logger.info(f"📊 Paper Trading账户已重置: ${bal:,.2f}")

    @safe_execute(default=None)
    def close(self):
        self._save_state()
        if self._conn:
            self._conn.close()
