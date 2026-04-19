"""
数据存储管理器 - SQLite
支持 K线、衍生品数据、配置、历史分析的存储
"""
import sqlite3
import json
import os
import time
from typing import Optional, List, Dict, Any, Union
from contextlib import contextmanager
from core.utils.logger import logger
from core.utils.helpers import safe_execute
from config.settings import DB_PATH


class DataBase:
    """SQLite 数据库管理器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    @contextmanager
    def get_cursor(self):
        """获取数据库游标的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库错误: {e}")
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """初始化数据库表"""
        with self.get_cursor() as cursor:
            # K线数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS klines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    open_time INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    close_time INTEGER NOT NULL,
                    quote_volume REAL,
                    trades INTEGER,
                    UNIQUE(exchange, symbol, interval, open_time)
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_klines_lookup 
                ON klines(exchange, symbol, interval, open_time)
            """)
            
            # 衍生品数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS derivatives_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    exchange TEXT,
                    data_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_derivatives_lookup 
                ON derivatives_data(symbol, data_type, timestamp)
            """)
            
            # 资金费率历史
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS funding_rates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    funding_rate REAL NOT NULL,
                    annual_rate REAL,
                    price REAL,
                    timestamp INTEGER NOT NULL,
                    UNIQUE(symbol, exchange, timestamp)
                )
            """)
            
            # 爆仓数据
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS liquidations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount_usd REAL NOT NULL,
                    price REAL NOT NULL,
                    timestamp INTEGER NOT NULL
                )
            """)
            
            # 分析结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    analysis_type TEXT NOT NULL,
                    result TEXT NOT NULL,
                    model_used TEXT,
                    timestamp INTEGER NOT NULL,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # 配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS configs (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            logger.info("数据库表初始化完成")
    
    # ==================== K线操作 ====================
    
    def save_klines(self, exchange: str, symbol: str, interval: str, klines: List[Dict]):
        """保存K线数据"""
        if not klines:
            return
        
        with self.get_cursor() as cursor:
            for k in klines:
                cursor.execute("""
                    INSERT OR REPLACE INTO klines 
                    (exchange, symbol, interval, open_time, open, high, low, close, volume, close_time, quote_volume, trades)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    exchange, symbol, interval,
                    k["open_time"], k["open"], k["high"], k["low"], k["close"], k["volume"],
                    k["close_time"], k.get("quote_volume"), k.get("trades")
                ))
        
        logger.debug(f"保存 {len(klines)} 条K线: {exchange} {symbol} {interval}")
    
    def get_klines(
        self,
        exchange: str,
        symbol: str,
        interval: str,
        start_time: int = None,
        end_time: int = None,
        limit: int = 1000
    ) -> List[Dict]:
        """获取K线数据"""
        with self.get_cursor() as cursor:
            sql = "SELECT * FROM klines WHERE exchange=? AND symbol=? AND interval=?"
            params = [exchange, symbol, interval]
            
            if start_time:
                sql += " AND open_time >= ?"
                params.append(start_time)
            if end_time:
                sql += " AND open_time <= ?"
                params.append(end_time)
            
            sql += " ORDER BY open_time DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            return [
                {
                    "open_time": r["open_time"],
                    "open": r["open"],
                    "high": r["high"],
                    "low": r["low"],
                    "close": r["close"],
                    "volume": r["volume"],
                    "close_time": r["close_time"],
                    "quote_volume": r["quote_volume"],
                    "trades": r["trades"],
                }
                for r in rows
            ]
    
    # ==================== 衍生品数据操作 ====================
    
    def save_derivatives_data(
        self,
        symbol: str,
        data_type: str,
        data: Dict,
        exchange: str = None
    ):
        """保存衍生品数据"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO derivatives_data (symbol, exchange, data_type, data, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (symbol, exchange, data_type, json.dumps(data), int(time.time() * 1000)))
        
        logger.debug(f"保存 {data_type} 数据: {symbol}")
    
    def save_funding_rates_batch(self, records: List[Dict]):
        """批量保存资金费率"""
        if not records:
            return
        with self.get_cursor() as cursor:
            for r in records:
                cursor.execute("""
                    INSERT OR IGNORE INTO funding_rates
                    (symbol, exchange, funding_rate, annual_rate, price, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    r.get('symbol', 'BTC'),
                    r.get('exchange', 'Binance'),
                    float(r.get('close', 0)),
                    None,
                    None,
                    r.get('time', 0)
                ))
        
        logger.debug(f"批量保存资金费率: {len(records)} 条")
    
    def get_latest_derivatives(
        self,
        symbol: str,
        data_type: str,
        hours: int = 24
    ) -> List[Dict]:
        """获取最近N小时的衍生品数据"""
        start_time = int((time.time() - hours * 3600) * 1000)
        
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM derivatives_data 
                WHERE symbol=? AND data_type=? AND timestamp>=?
                ORDER BY timestamp DESC
            """, (symbol, data_type, start_time))
            
            rows = cursor.fetchall()
            return [
                {"data": json.loads(r["data"]), "timestamp": r["timestamp"]}
                for r in rows
            ]
    
    # ==================== 资金费率操作 ====================
    
    def save_funding_rates(self, rates: List[Dict]):
        """批量保存资金费率"""
        with self.get_cursor() as cursor:
            for r in rates:
                cursor.execute("""
                    INSERT OR IGNORE INTO funding_rates 
                    (symbol, exchange, funding_rate, annual_rate, price, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    r["symbol"], r["exchange"], r["funding_rate"],
                    r.get("annual_rate"), r.get("price"), r["timestamp"]
                ))
    
    def get_funding_rate_history(
        self,
        symbol: str,
        exchange: str = None,
        days: int = 30
    ) -> List[Dict]:
        """获取资金费率历史"""
        start_time = int((time.time() - days * 86400) * 1000)
        
        with self.get_cursor() as cursor:
            if exchange:
                cursor.execute("""
                    SELECT * FROM funding_rates 
                    WHERE symbol=? AND exchange=? AND timestamp>=?
                    ORDER BY timestamp DESC
                """, (symbol, exchange, start_time))
            else:
                cursor.execute("""
                    SELECT * FROM funding_rates 
                    WHERE symbol=? AND timestamp>=?
                    ORDER BY timestamp DESC
                """, (symbol, start_time))
            
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    
    # ==================== 分析结果操作 ====================
    
    def save_analysis_result(
        self,
        symbol: str,
        analysis_type: str,
        result: Dict,
        model_used: str = None
    ):
        """保存分析结果"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO analysis_results (symbol, analysis_type, result, model_used, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (symbol, analysis_type, json.dumps(result), model_used, int(time.time() * 1000)))
    
    def get_analysis_history(
        self,
        symbol: str = None,
        analysis_type: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """获取分析历史"""
        with self.get_cursor() as cursor:
            sql = "SELECT * FROM analysis_results WHERE 1=1"
            params = []
            
            if symbol:
                sql += " AND symbol=?"
                params.append(symbol)
            if analysis_type:
                sql += " AND analysis_type=?"
                params.append(analysis_type)
            
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            return [
                {
                    "id": r["id"],
                    "symbol": r["symbol"],
                    "analysis_type": r["analysis_type"],
                    "result": json.loads(r["result"]),
                    "model_used": r["model_used"],
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]
    
    # ==================== 统计信息 ====================
    
    def get_stats(self) -> Dict[str, int]:
        """获取数据库统计信息"""
        with self.get_cursor() as cursor:
            stats = {}
            
            cursor.execute("SELECT COUNT(*) as cnt FROM klines")
            stats["klines"] = cursor.fetchone()["cnt"]
            
            cursor.execute("SELECT COUNT(*) as cnt FROM derivatives_data")
            stats["derivatives"] = cursor.fetchone()["cnt"]
            
            cursor.execute("SELECT COUNT(*) as cnt FROM funding_rates")
            stats["funding_rates"] = cursor.fetchone()["cnt"]
            
            cursor.execute("SELECT COUNT(*) as cnt FROM analysis_results")
            stats["analyses"] = cursor.fetchone()["cnt"]
            
            # 数据库大小
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            stats["db_size_bytes"] = db_size
            
            return stats


# 全局单例
_db = None


def get_db() -> DataBase:
    """获取数据库单例"""
    global _db
    if _db is None:
        _db = DataBase()
    return _db

# ==================== 扩展方法（供 cleaner/lifecycle 使用） ====================

# 包装器：给 DataBase 类添加缺失方法
_original_init = DataBase.__init__

def _extended_init(self, db_path=DB_PATH):
    _original_init(self, db_path)

DataBase.__init__ = _extended_init

@safe_execute(default=0)
def get_latest_timestamp(self, symbol: str, interval: str) -> Optional[float]:
    """获取最新K线时间戳"""
    with self.get_cursor() as (conn, cursor):
        cursor.execute(
            "SELECT MAX(open_time) as latest FROM klines WHERE symbol = ? AND interval = ?",
            (symbol, interval)
        )
        row = cursor.fetchone()
        return row['latest'] if row and row['latest'] else None

DataBase.get_latest_timestamp = get_latest_timestamp

@safe_execute(default=[])
def get_data_before(self, category: str, cutoff: int) -> List[Dict]:
    """获取指定时间之前的数据"""
    with self.get_cursor() as (conn, cursor):
        cursor.execute(
            "SELECT * FROM klines WHERE open_time < ? LIMIT 10000",
            (cutoff,)
        )
        return [dict(row) for row in cursor.fetchall()]

DataBase.get_data_before = get_data_before

@safe_execute(default={'rows': 0, 'mb': 0})
def delete_data_before(self, category: str, cutoff: int) -> Dict:
    """删除指定时间之前的数据"""
    with self.get_cursor() as (conn, cursor):
        cursor.execute("SELECT COUNT(*) as cnt FROM klines WHERE open_time < ?", (cutoff,))
        count = cursor.fetchone()['cnt']
        cursor.execute("DELETE FROM klines WHERE open_time < ?", (cutoff,))
        conn.commit()
    return {'rows': count, 'mb': count * 0.001}

DataBase.delete_data_before = delete_data_before

def get_storage(self):
    return self

DataBase.get_storage = get_storage
