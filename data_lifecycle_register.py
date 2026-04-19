#!/usr/bin/env python3
"""
数据生命周期注册脚本
将所有现有数据表注册到 IntelligentDataCleaner
"""
import sqlite3, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")

def get_tables(db_path):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in c.fetchall()]
        conn.close()
        return tables
    except Exception:
        return []

def guess_ts_column(db_path, table):
    for col in ["timestamp", "ts", "created_at", "datetime", "date"]:
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL LIMIT 1")
            if c.fetchone()[0] > 0:
                conn.close()
                return col
            conn.close()
        except Exception:
            pass
    return "timestamp"

def get_row_count(db_path, table):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0

def register_all():
    from core.analysis.validation.data_cleaner import get_data_cleaner
    cleaner = get_data_cleaner()

    db_type_map = {
        "cryptomind.db": {
            "klines": "klines_4h", "funding_rate": "funding_rate",
            "open_interest": "open_interest", "long_short_ratio": "long_short_ratio",
            "liquidation": "liquidation", "derivatives": "funding_rate",
        },
        "knowledge.db": {"patterns": "patterns"},
        "validation.db": {"predictions": "validations", "validations": "validations"},
        "attribution.db": {"attribution_results": "attributions"},
        "evolution.db": {"evolution_cycles": "patterns", "strategy_versions": "patterns"},
        "signal_history.db": {"signals": "signals"},
        "cleaner.db": None,
    }

    print("🔍 扫描数据文件...")
    total = 0

    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith(".db"):
            continue
        db_path = os.path.join(DATA_DIR, fname)
        tables = get_tables(db_path)
        type_map = db_type_map.get(fname, {})

        for table in tables:
            data_type = None
            for t_name, d_type in type_map.items():
                if t_name in table.lower():
                    data_type = d_type
                    break

            if data_type is None:
                if "kline" in table.lower() or "candle" in table.lower(): data_type = "klines_4h"
                elif "funding" in table.lower(): data_type = "funding_rate"
                elif "oi" in table.lower() or "interest" in table.lower(): data_type = "open_interest"
                elif "liq" in table.lower(): data_type = "liquidation"
                elif "news" in table.lower(): data_type = "news"
                elif "onchain" in table.lower(): data_type = "onchain_eth"
                elif "signal" in table.lower(): data_type = "signals"
                elif "pattern" in table.lower(): data_type = "patterns"
                elif "validation" in table.lower(): data_type = "validations"
                elif "attr" in table.lower(): data_type = "attributions"
                else: continue

            ts_col = guess_ts_column(db_path, table)
            rows = get_row_count(db_path, table)
            cleaner.register_table(data_type, db_path, table, ts_col)
            pct = rows / 10000 * 100
            icon = "🔴" if pct > 80 else ("🟡" if pct > 50 else "🟢")
            print(f"  {icon} {fname:<25}.{table:<30} → {data_type:<20} {rows:>6,}行")
            total += 1

    print(f"\n📊 共注册 {total} 个数据表")

    report = cleaner.get_storage_report()
    print(f"\n📦 存储报告 ({report['tables']} 个表, {report['total_rows']:,} 总行):")
    for item in report["report"]:
        icon = "🔴" if item["usage_pct"] > 80 else ("🟡" if item["usage_pct"] > 50 else "🟢")
        print(f"  {icon} {item['data_type']:<25} {item['rows']:>8,} / {item['max_rows']:>8,} ({item['usage_pct']}%) {item['status']}")

    cleaner.close()
    return total

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    count = register_all()
    print(f"\n✅ 完成! 注册了 {count} 个表")
