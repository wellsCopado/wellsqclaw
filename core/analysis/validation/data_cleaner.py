"""
智能数据清洗器 - IntelligentDataCleaner
三维清理策略：使用频率 × 重要性 × 存储成本
支持18种数据类型的保留策略
"""
import sqlite3
import time
import os
from typing import Optional
from dataclasses import dataclass
from core.utils.logger import logger
from core.utils.helpers import safe_execute


@dataclass
class RetentionPolicy:
    """数据保留策略"""
    data_type: str
    max_age_days: int       # 最大保留天数
    max_rows: int           # 最大行数
    importance: float       # 重要性 0-1
    compress_after_days: int  # N天后压缩
    description: str


# ─────────────────────────────────────────────────────────────
# 18种数据类型保留策略
# ─────────────────────────────────────────────────────────────
RETENTION_POLICIES = {
    # 现货K线
    "klines_1m":   RetentionPolicy("klines_1m",   3,    10000, 0.3, 1,   "1分钟K线"),
    "klines_5m":   RetentionPolicy("klines_5m",   7,    20000, 0.4, 2,   "5分钟K线"),
    "klines_15m":  RetentionPolicy("klines_15m",  14,   20000, 0.5, 3,   "15分钟K线"),
    "klines_1h":   RetentionPolicy("klines_1h",   30,   10000, 0.7, 7,   "1小时K线"),
    "klines_4h":   RetentionPolicy("klines_4h",   90,   5000,  0.8, 14,  "4小时K线"),
    "klines_1d":   RetentionPolicy("klines_1d",   365,  2000,  0.9, 30,  "日K线"),

    # 衍生品数据
    "funding_rate":     RetentionPolicy("funding_rate",     90,  50000, 0.9, 14, "资金费率"),
    "open_interest":    RetentionPolicy("open_interest",    90,  50000, 0.8, 14, "持仓量"),
    "liquidation":      RetentionPolicy("liquidation",      30,  20000, 0.7, 7,  "爆仓数据"),
    "long_short_ratio": RetentionPolicy("long_short_ratio", 60,  30000, 0.7, 14, "多空比"),

    # 链上数据
    "onchain_eth":  RetentionPolicy("onchain_eth",  30,  10000, 0.6, 7,  "ETH链上数据"),
    "onchain_btc":  RetentionPolicy("onchain_btc",  30,  10000, 0.6, 7,  "BTC链上数据"),

    # 新闻情感
    "news":         RetentionPolicy("news",         7,   5000,  0.5, 2,  "新闻数据"),
    "sentiment":    RetentionPolicy("sentiment",    30,  10000, 0.6, 7,  "情感分析"),

    # 分析结果
    "signals":      RetentionPolicy("signals",      180, 20000, 1.0, 30, "交易信号"),
    "patterns":     RetentionPolicy("patterns",     365, 10000, 1.0, 60, "成功模式"),
    "validations":  RetentionPolicy("validations",  365, 10000, 1.0, 60, "验证结果"),
    "attributions": RetentionPolicy("attributions", 365, 10000, 1.0, 60, "归因分析"),
}


class IntelligentDataCleaner:
    """
    智能数据清洗器

    三维清理策略：
    1. 使用频率 - 最近访问时间
    2. 重要性 - 数据类型权重
    3. 存储成本 - 行数/大小

    支持：
    - 自动清理过期数据
    - 按重要性保留关键数据
    - 存储空间监控
    - 清理报告
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base, "data", "cleaner.db")
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
            CREATE TABLE IF NOT EXISTS clean_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_type TEXT,
                rows_deleted INTEGER,
                bytes_freed INTEGER,
                reason TEXT,
                cleaned_at INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS data_registry (
                data_type TEXT PRIMARY KEY,
                total_rows INTEGER,
                oldest_ts INTEGER,
                newest_ts INTEGER,
                last_accessed INTEGER,
                db_path TEXT,
                table_name TEXT
            )
        """)
        conn.commit()
        logger.info(f"数据清洗器初始化: {self.db_path}")

    def register_table(
        self,
        data_type: str,
        db_path: str,
        table_name: str,
        ts_column: str = "timestamp"
    ):
        """注册一个需要管理的数据表"""
        conn = self._get_conn()
        c = conn.cursor()

        # 获取表统计
        try:
            target_conn = sqlite3.connect(db_path)
            tc = target_conn.cursor()
            tc.execute(f"SELECT COUNT(*), MIN({ts_column}), MAX({ts_column}) FROM {table_name}")
            row = tc.fetchone()
            total = row[0] if row else 0
            oldest = row[1] if row else 0
            newest = row[2] if row else 0
            target_conn.close()
        except Exception:
            total, oldest, newest = 0, 0, 0

        c.execute("""
            INSERT OR REPLACE INTO data_registry
            (data_type, total_rows, oldest_ts, newest_ts, last_accessed, db_path, table_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (data_type, total, oldest, newest, int(time.time()), db_path, table_name))
        conn.commit()

    def calculate_priority_score(self, data_type: str, row_count: int, age_days: float) -> float:
        """
        计算数据优先级分数（越高越应该保留）

        公式：priority = importance × (1 / age_factor) × (1 / size_factor)
        """
        policy = RETENTION_POLICIES.get(data_type)
        if not policy:
            return 0.5

        # 重要性因子
        importance = policy.importance

        # 年龄因子（越老越低）
        age_factor = max(age_days / policy.max_age_days, 0.01)

        # 大小因子（越大越低）
        size_factor = max(row_count / policy.max_rows, 0.01)

        priority = importance / (age_factor * size_factor)
        return min(priority, 100.0)

    def clean_table(
        self,
        db_path: str,
        table_name: str,
        data_type: str,
        ts_column: str = "timestamp",
        dry_run: bool = False,
    ) -> dict:
        """
        清理单个数据表

        Returns:
            清理报告 {rows_deleted, bytes_freed, reason}
        """
        policy = RETENTION_POLICIES.get(data_type)
        if not policy:
            return {"rows_deleted": 0, "reason": f"未知数据类型: {data_type}"}

        try:
            target_conn = sqlite3.connect(db_path)
            tc = target_conn.cursor()

            # 当前状态
            tc.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_rows = tc.fetchone()[0]

            deleted = 0
            reasons = []

            # 策略1: 删除超龄数据
            cutoff_ts = int(time.time()) - policy.max_age_days * 86400
            if not dry_run:
                tc.execute(f"DELETE FROM {table_name} WHERE {ts_column} < ?", (cutoff_ts,))
                age_deleted = tc.rowcount
            else:
                tc.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {ts_column} < ?", (cutoff_ts,))
                age_deleted = tc.fetchone()[0]

            if age_deleted > 0:
                deleted += age_deleted
                reasons.append(f"超龄删除{age_deleted}行(>{policy.max_age_days}天)")

            # 策略2: 超量删除（保留最新的 max_rows 行）
            remaining = total_rows - age_deleted
            if remaining > policy.max_rows:
                excess = remaining - policy.max_rows
                if not dry_run:
                    tc.execute(f"""
                        DELETE FROM {table_name}
                        WHERE rowid IN (
                            SELECT rowid FROM {table_name}
                            ORDER BY {ts_column} ASC
                            LIMIT ?
                        )
                    """, (excess,))
                    size_deleted = tc.rowcount
                else:
                    size_deleted = excess

                if size_deleted > 0:
                    deleted += size_deleted
                    reasons.append(f"超量删除{size_deleted}行(>{policy.max_rows}行)")

            if not dry_run:
                target_conn.commit()
                # VACUUM 释放空间
                if deleted > 1000:
                    target_conn.execute("VACUUM")

            target_conn.close()

            # 记录清理日志
            if not dry_run and deleted > 0:
                conn = self._get_conn()
                c = conn.cursor()
                c.execute("""
                    INSERT INTO clean_log (data_type, rows_deleted, bytes_freed, reason, cleaned_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (data_type, deleted, deleted * 100, " | ".join(reasons), int(time.time())))
                conn.commit()

            return {
                "data_type": data_type,
                "table": table_name,
                "rows_before": total_rows,
                "rows_deleted": deleted,
                "rows_after": total_rows - deleted,
                "reason": " | ".join(reasons) if reasons else "无需清理",
                "dry_run": dry_run,
            }

        except Exception as e:
            logger.error(f"清理失败 [{data_type}]: {e}")
            return {"data_type": data_type, "error": str(e), "rows_deleted": 0}

    def run_full_clean(self, dry_run: bool = False) -> dict:
        """
        执行全量清理

        扫描所有注册的数据表，按策略清理
        """
        logger.info(f"🧹 开始{'模拟' if dry_run else ''}全量数据清理...")

        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM data_registry")
        registries = c.fetchall()

        results = []
        total_deleted = 0

        for reg in registries:
            data_type = reg["data_type"]
            db_path = reg["db_path"]
            table_name = reg["table_name"]

            result = self.clean_table(db_path, table_name, data_type, dry_run=dry_run)
            results.append(result)
            total_deleted += result.get("rows_deleted", 0)

        logger.info(f"🧹 清理完成: 共删除 {total_deleted} 行")

        return {
            "total_deleted": total_deleted,
            "tables_cleaned": len(results),
            "dry_run": dry_run,
            "details": results,
            "timestamp": int(time.time()),
        }

    def get_storage_report(self) -> dict:
        """获取存储使用报告"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM data_registry ORDER BY total_rows DESC")
        registries = c.fetchall()

        report = []
        total_rows = 0

        for reg in registries:
            data_type = reg["data_type"]
            policy = RETENTION_POLICIES.get(data_type, {})
            rows = reg["total_rows"] or 0
            total_rows += rows

            # 计算使用率
            max_rows = getattr(policy, "max_rows", 10000) if policy else 10000
            usage_pct = round(rows / max_rows * 100, 1) if max_rows > 0 else 0

            report.append({
                "data_type": data_type,
                "rows": rows,
                "max_rows": max_rows,
                "usage_pct": usage_pct,
                "importance": getattr(policy, "importance", 0.5) if policy else 0.5,
                "status": "⚠️ 接近上限" if usage_pct > 80 else "✅ 正常",
            })

        # 最近清理记录
        c.execute("SELECT * FROM clean_log ORDER BY cleaned_at DESC LIMIT 10")
        recent_cleans = [dict(row) for row in c.fetchall()]

        return {
            "total_rows": total_rows,
            "tables": len(report),
            "report": report,
            "recent_cleans": recent_cleans,
        }

    def get_clean_history(self, limit: int = 20) -> list:
        """获取清理历史"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM clean_log ORDER BY cleaned_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in c.fetchall()]


    def auto_cleanup(self, table_name: str = None, days: int = 90) -> dict:
        """自动清理过期数据（默认90天）"""
        import time as _t
        cutoff = int(_t.time()) - days * 86400
        conn = self._get_conn()
        c = conn.cursor()
        results = {}
        tables = [table_name] if table_name else self._get_managed_tables()
        for tbl in tables:
            try:
                c.execute(f'DELETE FROM {tbl} WHERE created_at < ? AND created_at > 0', (cutoff,))
                deleted = c.rowcount
                results[tbl] = {'deleted': deleted, 'cutoff_days': days}
            except Exception as e:
                results[tbl] = {'error': str(e)}
        conn.commit()
        logger.info(f'Auto cleanup: {results}')
        return results

    def get_retention_stats(self) -> dict:
        """获取各表数据保留统计"""
        import time as _t
        conn = self._get_conn()
        c = conn.cursor()
        now = int(_t.time())
        stats = {}
        for tbl in self._get_managed_tables():
            try:
                c.execute(f'SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM {tbl}')
                row = c.fetchone()
                if row and row[0] > 0:
                    oldest_days = (now - (row[1] or now)) / 86400
                    newest_days = (now - (row[2] or now)) / 86400
                    stats[tbl] = {
                        'total': row[0],
                        'oldest_days': round(oldest_days, 1),
                        'newest_days': round(newest_days, 1)
                    }
            except Exception:
                pass
        return stats

    def _get_managed_tables(self) -> list:
        """获取受管理的表列表"""
        return [
            'derivatives_data', 'funding_rates', 'klines_4h',
            'liquidations', 'evolution_cycles', 'strategy_versions',
            'patterns', 'feedback_entries', 'model_usage'
        ]

    @safe_execute(default=None)
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


_cleaner: Optional[IntelligentDataCleaner] = None


def get_data_cleaner() -> IntelligentDataCleaner:
    global _cleaner
    if _cleaner is None:
        _cleaner = IntelligentDataCleaner()
    return _cleaner
