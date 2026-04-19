"""
知识库系统 - 成功模式积累与检索
基于 SQLite + sqlite-vss 向量搜索
存储成功/失败交易模式，支持语义相似度检索
"""
import sqlite3
import json
import time
import hashlib
import math
from typing import Optional, Any, List, Dict, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from core.utils.logger import logger
from core.utils.helpers import safe_execute


# ─────────────────────────────────────────────────────────────
# 简单的词向量嵌入 (不使用外部ML库)
# 基于TF-IDF + 预定义词表
# ─────────────────────────────────────────────────────────────
_CRYPTO_VOCAB = {
    # 市场状态
    "bullish": [0.1, 0.2, 0.3], "bearish": [-0.1, -0.2, -0.3],
    "neutral": [0.0, 0.0, 0.0], "sideways": [0.0, 0.05, 0.0],
    "uptrend": [0.15, 0.25, 0.3], "downtrend": [-0.15, -0.25, -0.3],
    # 信号
    "buy": [0.2, 0.1, 0.4], "sell": [-0.2, -0.1, -0.4],
    "strong_buy": [0.3, 0.15, 0.5], "strong_sell": [-0.3, -0.15, -0.5],
    "hold": [0.0, 0.0, 0.1],
    # 指标
    "rsi_overbought": [-0.1, 0.0, -0.3], "rsi_oversold": [0.1, 0.0, 0.3],
    "rsi_neutral": [0.0, 0.0, 0.0],
    "macd_bullish": [0.15, 0.1, 0.2], "macd_bearish": [-0.15, -0.1, -0.2],
    "macd_cross": [0.05, 0.05, 0.15],
    "bollinger_expand": [0.0, 0.1, 0.0], "bollinger_squeeze": [0.0, -0.1, 0.0],
    "ema_bullish": [0.1, 0.15, 0.2], "ema_bearish": [-0.1, -0.15, -0.2],
    # 市场情绪
    "fear": [-0.2, -0.1, -0.2], "greed": [0.2, 0.1, 0.2],
    "funding_positive": [-0.1, 0.0, -0.1], "funding_negative": [0.1, 0.0, 0.1],
    "high_volume": [0.1, 0.15, 0.2], "low_volume": [-0.05, -0.05, -0.05],
    # 风险
    "high_risk": [-0.2, 0.1, -0.3], "medium_risk": [0.0, 0.0, 0.0], "low_risk": [0.1, -0.05, 0.1],
    # 模式
    "reversal": [0.1, 0.2, 0.3], "continuation": [0.05, 0.05, 0.1],
    "breakout": [0.15, 0.2, 0.25], "breakdown": [-0.15, -0.2, -0.25],
    "support": [0.1, 0.0, 0.15], "resistance": [-0.1, 0.0, -0.15],
    # 时间
    "short_term": [0.05, 0.0, 0.0], "medium_term": [0.0, 0.1, 0.0], "long_term": [-0.05, 0.15, 0.05],
}


def _tokenize(text: str) -> List[str]:
    """简单分词"""
    return text.lower().replace("/", " ").replace("_", " ").split()


def _text_to_embedding(text: str, dim: int = 16) -> List[float]:
    """将文本转换为固定维度向量"""
    tokens = _tokenize(text)
    vec = [0.0] * dim

    for token in tokens:
        if token in _CRYPTO_VOCAB:
            base = _CRYPTO_VOCAB[token]
            for i in range(min(dim, len(base))):
                vec[i] += base[i]

    # 归一化
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]

    return vec


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算余弦相似度"""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a * norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _vec_to_hex(vec: List[float]) -> str:
    """向量转为16进制字符串存储"""
    import struct
    data = struct.pack(f'{len(vec)}f', *vec)
    return data.hex()


def _hex_to_vec(hex_str: str) -> List[float]:
    """从16进制恢复向量"""
    import struct
    data = bytes.fromhex(hex_str)
    num = len(data) // 4
    return list(struct.unpack(f'{num}f', data))


# ─────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────
@dataclass
class Pattern:
    """成功/失败模式"""
    id: str
    pattern_type: str         # success / failure / neutral
    symbol: str
    timeframe: str
    created_at: int

    # 信号特征
    signal: str               # BUY / SELL / NEUTRAL
    signal_score: float

    # 技术指标快照
    rsi: float
    macd_hist: float
    bb_position: float
    ema_alignment: str

    # 市场背景
    trend: str
    funding_rate: float
    market_sentiment: str

    # 交易结果
    entry_price: float
    exit_price: float
    profit_pct: float
    holding_hours: float

    # 描述
    description: str
    key_factors: str
    outcome_verdict: str

    # 向量
    keywords_hash: str
    metadata: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────
# 知识库核心
# ─────────────────────────────────────────────────────────────
class KnowledgeBase:
    """
    知识库 - 存储和分析成功/失败模式
    集成 sqlite-vss 向量搜索
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            import os
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base, "data", "knowledge.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._vector_dim = 16
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        """初始化数据库 + sqlite-vss"""
        conn = self._get_conn()
        c = conn.cursor()

        # 主表
        c.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                created_at INTEGER NOT NULL,

                signal TEXT NOT NULL,
                signal_score REAL NOT NULL,

                rsi REAL,
                macd_hist REAL,
                bb_position REAL,
                ema_alignment TEXT,

                trend TEXT,
                funding_rate REAL,
                market_sentiment TEXT,

                entry_price REAL,
                exit_price REAL,
                profit_pct REAL,
                holding_hours REAL,

                description TEXT,
                key_factors TEXT,
                outcome_verdict TEXT,

                keywords_hash TEXT,
                metadata TEXT DEFAULT ''
            )
        """)

        # 普通索引
        c.execute("CREATE INDEX IF NOT EXISTS idx_pattern_type ON patterns(pattern_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON patterns(symbol)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_signal ON patterns(signal)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_profit ON patterns(profit_pct)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_created ON patterns(created_at)")

        # ── sqlite-vss 向量搜索 ──
        self._setup_vss(c)

        conn.commit()
        logger.info(f"知识库初始化完成: {self.db_path}")

    def _setup_vss(self, c: sqlite3.Cursor):
        """设置 sqlite-vss 向量表"""
        try:
            # 尝试加载 sqlite-vss 扩展
            c.execute("SELECT vss_version()")
            vss_available = True
            logger.info("✅ sqlite-vss 可用，启用向量搜索")
        except Exception:
            vss_available = False
            logger.warning("⚠️ sqlite-vss 不可用，使用余弦相似度计算替代")
            return

        if vss_available:
            try:
                dim = self._vector_dim
                c.execute(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS patterns_vss USING vss0(
                        embedding({dim})
                    )
                """)

                # 尝试插入一条测试数据验证
                test_vec = [0.0] * dim
                c.execute(f"INSERT INTO patterns_vss(rowid, embedding) VALUES(0, vss0_fvec(?))", (_vec_to_hex(test_vec),))
                c.execute("DELETE FROM patterns_vss WHERE rowid = 0")
                conn = self._get_conn()
                conn.commit()
                self._vss_available = True
                logger.info(f"✅ sqlite-vss 向量表创建成功 (维度={dim})")
            except Exception as e:
                logger.warning(f"⚠️ sqlite-vss 向量表创建失败: {e}，使用替代方案")
                self._vss_available = False

    def _generate_embedding(self, pattern: Pattern) -> List[float]:
        """为模式生成向量嵌入"""
        # 组合所有文本特征
        text_parts = [
            pattern.signal,
            pattern.trend,
            pattern.market_sentiment,
            pattern.ema_alignment,
            pattern.outcome_verdict,
            pattern.key_factors or "",
            pattern.pattern_type,
            f"rsi_{'overbought' if pattern.rsi > 70 else 'oversold' if pattern.rsi < 30 else 'neutral'}",
            f"bb_{'high' if pattern.bb_position > 80 else 'low' if pattern.bb_position < 20 else 'mid'}",
            f"profit_{'positive' if pattern.profit_pct > 0 else 'negative'}",
        ]
        combined = " ".join(str(p) for p in text_parts if p)
        return _text_to_embedding(combined, self._vector_dim)

    def _generate_hash(self, pattern: Pattern) -> str:
        """生成关键词哈希"""
        key_parts = [
            pattern.symbol, pattern.timeframe, pattern.signal,
            pattern.trend, pattern.market_sentiment,
            f"{pattern.rsi:.0f}", f"{pattern.bb_position:.0f}",
            pattern.ema_alignment
        ]
        combined = "|".join(str(p) for p in key_parts)
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def add_pattern(
        self,
        symbol: str,
        timeframe: str,
        signal: str,
        signal_score: float,
        indicators: Dict,
        market: Dict,
        result: Dict,
        description: str = "",
        key_factors: str = "",
        outcome_verdict: str = "PENDING",
    ) -> str:
        """添加新的成功/失败模式"""
        conn = self._get_conn()
        c = conn.cursor()

        pattern = Pattern(
            id="",
            pattern_type="success" if outcome_verdict == "SUCCESS" else "failure" if outcome_verdict == "FAILURE" else "neutral",
            symbol=symbol,
            timeframe=timeframe,
            created_at=int(time.time()),
            signal=signal,
            signal_score=signal_score,
            rsi=indicators.get("rsi", 50),
            macd_hist=indicators.get("macd_hist", 0),
            bb_position=indicators.get("bb_position", 50),
            ema_alignment=indicators.get("ema_alignment", "混乱"),
            trend=market.get("trend", "SIDEWAYS"),
            funding_rate=market.get("funding_rate", 0),
            market_sentiment=market.get("sentiment", "neutral"),
            entry_price=result.get("entry_price", 0),
            exit_price=result.get("exit_price", 0),
            profit_pct=result.get("profit_pct", 0),
            holding_hours=result.get("holding_hours", 0),
            description=description,
            key_factors=key_factors,
            outcome_verdict=outcome_verdict,
            keywords_hash="",
            metadata=json.dumps({
                "pattern_score": signal_score,
                "confidence": indicators.get("confidence", 0),
                "risk": indicators.get("risk", "medium"),
            }, ensure_ascii=False),
        )

        pattern.keywords_hash = self._generate_hash(pattern)
        pattern.id = hashlib.sha1(
            f"{pattern.keywords_hash}{time.time()}".encode()
        ).hexdigest()[:16]

        # 生成向量
        embedding = self._generate_embedding(pattern)
        embedding_hex = _vec_to_hex(embedding)

        c.execute("""
            INSERT INTO patterns (
                id, pattern_type, symbol, timeframe, created_at,
                signal, signal_score, rsi, macd_hist, bb_position,
                ema_alignment, trend, funding_rate, market_sentiment,
                entry_price, exit_price, profit_pct, holding_hours,
                description, key_factors, outcome_verdict,
                keywords_hash, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pattern.id, pattern.pattern_type, pattern.symbol, pattern.timeframe,
            pattern.created_at, pattern.signal, pattern.signal_score,
            pattern.rsi, pattern.macd_hist, pattern.bb_position,
            pattern.ema_alignment, pattern.trend, pattern.funding_rate,
            pattern.market_sentiment, pattern.entry_price, pattern.exit_price,
            pattern.profit_pct, pattern.holding_hours, pattern.description,
            pattern.key_factors, pattern.outcome_verdict,
            pattern.keywords_hash, pattern.metadata,
        ))

        # 向量同步到 vss 表
        if getattr(self, '_vss_available', False):
            try:
                rowid = c.lastrowid
                c.execute(
                    "INSERT INTO patterns_vss(rowid, embedding) VALUES(?, vss0_fvec(?))",
                    (rowid, embedding_hex)
                )
            except Exception as e:
                logger.warning(f"向量插入失败: {e}")

        conn.commit()
        logger.info(f"模式已存储: {pattern.id} ({pattern.pattern_type}) {symbol}")
        return pattern.id

    def find_similar(
        self,
        signal: str,
        trend: str,
        sentiment: str,
        rsi: float,
        bb_pos: float,
        limit: int = 5,
    ) -> List[Dict]:
        """
        查找相似模式（核心功能）
        1. sqlite-vss 向量搜索（如果可用）
        2. 余弦相似度计算（降级方案）
        """
        conn = self._get_conn()
        c = conn.cursor()

        # 生成查询向量
        query_text = f"{signal} {trend} {sentiment} rsi_{'overbought' if rsi > 70 else 'oversold' if rsi < 30 else 'neutral'} bb_{'high' if bb_pos > 80 else 'low' if bb_pos < 20 else 'mid'}"
        query_vec = _text_to_embedding(query_text, self._vector_dim)
        query_hex = _vec_to_hex(query_vec)

        results = []

        # ── sqlite-vss 向量搜索 ──
        if getattr(self, '_vss_available', False):
            try:
                # 先同步向量表（可能有遗漏）
                c.execute("""
                    SELECT rowid, embedding FROM patterns_vss vss
                    WHERE rowid NOT IN (SELECT rowid FROM patterns)
                """)
                orphaned = c.fetchall()
                for row in orphaned:
                    c.execute("DELETE FROM patterns_vss WHERE rowid = ?", (row["rowid"],))

                # 向量最近邻搜索
                c.execute("""
                    SELECT p.*, vss0_distance(embedding) as dist
                    FROM patterns p
                    JOIN patterns_vss v ON p.rowid = v.rowid
                    WHERE vss0_search(embedding, vss0_fvec(?)) AND p.outcome_verdict != 'PENDING'
                    ORDER BY dist ASC
                    LIMIT ?
                """, (query_hex, limit))

                for row in c.fetchall():
                    results.append(dict(row))
            except Exception as e:
                logger.warning(f"sqlite-vss 搜索失败: {e}，使用降级方案")
                self._vss_available = False

        # ── 降级：余弦相似度计算 ──
        if not results:
            c.execute("""
                SELECT * FROM patterns
                WHERE outcome_verdict != 'PENDING'
                ORDER BY created_at DESC
                LIMIT 200
            """)
            rows = c.fetchall()

            scored = []
            for row in rows:
                row_dict = dict(row)
                # 从 keywords_hash 字段读取嵌入（如果存在）
                stored_hex = row_dict.get("keywords_hash", "")
                if stored_hex and len(stored_hex) >= self._vector_dim * 8:
                    stored_vec = _hex_to_vec(stored_hex[:self._vector_dim * 8])
                else:
                    # 重新生成（只取Pattern支持的字段）
                    from dataclasses import fields
                    valid = {f.name for f in fields(Pattern)}
                    filtered = {k: v for k, v in row_dict.items()
                                if k in valid and k != 'metadata'}
                    p = Pattern(**filtered)
                    stored_vec = self._generate_embedding(p)

                similarity = _cosine_similarity(query_vec, stored_vec)
                row_dict["similarity"] = similarity
                scored.append((similarity, row_dict))

            scored.sort(key=lambda x: x[0], reverse=True)
            results = [r for _, r in scored[:limit]]

        # 格式化结果
        formatted = []
        for r in results:
            formatted.append({
                "id": r["id"],
                "pattern_type": r["pattern_type"],
                "symbol": r["symbol"],
                "timeframe": r["timeframe"],
                "signal": r["signal"],
                "profit_pct": round(r.get("profit_pct", 0), 2),
                "outcome": r["outcome_verdict"],
                "similarity": round(r.get("similarity", 0), 3),
                "rsi": r.get("rsi", 50),
                "trend": r.get("trend", "SIDEWAYS"),
                "description": r.get("description", ""),
                "key_factors": r.get("key_factors", ""),
                "created_at": r.get("created_at", 0),
            })

        return formatted

    def generate_enhanced_prompt(self, symbol: str, timeframe: str) -> str:
        """从知识库生成增强提示词"""
        conn = self._get_conn()
        c = conn.cursor()

        # 获取最近成功模式
        c.execute("""
            SELECT * FROM patterns
            WHERE symbol = ? AND timeframe = ?
              AND pattern_type = 'success'
              AND outcome_verdict = 'SUCCESS'
            ORDER BY profit_pct DESC, created_at DESC
            LIMIT 3
        """, (symbol, timeframe))
        success_rows = c.fetchall()

        # 获取整体统计
        c.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN pattern_type = 'success' THEN 1 ELSE 0 END) as successes,
                AVG(CASE WHEN pattern_type = 'success' THEN profit_pct ELSE NULL END) as avg_profit,
                AVG(CASE WHEN pattern_type = 'failure' THEN profit_pct ELSE NULL END) as avg_loss
            FROM patterns
            WHERE symbol = ? AND timeframe = ?
              AND outcome_verdict != 'PENDING'
        """, (symbol, timeframe))
        stats = dict(c.fetchone())

        if not success_rows and stats["total"] == 0:
            return ""

        lines = ["\n[来自知识库的历史分析]"]

        if stats["total"] > 0:
            win_rate = (stats["successes"] or 0) / stats["total"] * 100
            lines.append(f"- {symbol} {timeframe} 历史胜率: {win_rate:.0f}%")
            if stats["avg_profit"]:
                lines.append(f"- 成功交易平均盈利: +{stats['avg_profit']:.2f}%")
            if stats["avg_loss"]:
                lines.append(f"- 失败交易平均亏损: {stats['avg_loss']:.2f}%")

        if success_rows:
            lines.append(f"\n最近成功模式 ({len(success_rows)}个):")
            for row in success_rows[:2]:
                d = dict(row)
                factors = d.get("key_factors", "") or ""
                desc = d.get("description", "") or ""
                lines.append(f"  • {d['signal']} | RSI={d['rsi']:.0f} | 盈{d['profit_pct']:+.2f}% | {factors or desc}")

        return "\n".join(lines)

    def get_statistics(self) -> Dict:
        """获取知识库统计"""
        conn = self._get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN pattern_type = 'success' THEN 1 ELSE 0 END) as successes,
                SUM(CASE WHEN pattern_type = 'failure' THEN 1 ELSE 0 END) as failures,
                SUM(CASE WHEN pattern_type = 'neutral' THEN 1 ELSE 0 END) as neutrals,
                AVG(CASE WHEN pattern_type = 'success' THEN profit_pct ELSE NULL END) as avg_success_profit,
                AVG(CASE WHEN pattern_type = 'failure' THEN profit_pct ELSE NULL END) as avg_failure_loss,
                COUNT(DISTINCT symbol) as symbols_count
            FROM patterns
        """)
        stats = dict(c.fetchone())

        total = stats["total"] or 0
        successes = stats["successes"] or 0
        win_rate = (successes / total * 100) if total > 0 else 0.0

        return {
            "total_patterns": total,
            "successes": successes,
            "failures": stats["failures"] or 0,
            "neutrals": stats["neutrals"] or 0,
            "win_rate": round(win_rate, 1),
            "avg_profit_success": round(stats["avg_success_profit"] or 0, 2),
            "avg_loss_failure": round(stats["avg_failure_loss"] or 0, 2),
            "symbols_count": stats["symbols_count"] or 0,
            "vector_dimension": self._vector_dim,
            "vss_enabled": getattr(self, '_vss_available', False),
        }

    @safe_execute(default=None)
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

# ─────────────────────────────────────────────────────────────────
# 单例访问器（供其他模块使用）
# ─────────────────────────────────────────────────────────────────
_kb_instance = None

def get_knowledge_base() -> KnowledgeBase:
    """返回知识库单例实例"""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = KnowledgeBase()
    return _kb_instance
