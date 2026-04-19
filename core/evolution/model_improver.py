"""
模型改进器 (Model Improver)
分析模型表现，决定是否切换/调整模型参数
支持本地模型 + 云端API 自动降级
"""
import sqlite3
import json
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from core.utils.logger import logger
from core.utils.helpers import safe_execute


class ModelType(Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    RULE = "rule"


@dataclass
class ModelConfig:
    """模型配置"""
    id: str
    name: str
    model_type: ModelType
    provider: str       # ollama / openai / anthropic / rule
    model_name: str     # gemma3:4b / gpt-4 / claude-3

    # 性能参数
    avg_latency: float  # 秒
    avg_score: float     # 0-100
    success_rate: float  # 预测准确率

    # 成本
    cost_per_1k: float  # $ per 1000 tokens
    is_active: bool = True
    priority: int = 0    # 优先级（数字越小越优先）


@dataclass
class ModelCall:
    """模型调用记录"""
    id: str
    model_id: str
    model_name: str
    symbol: str
    call_type: str      # analysis / prediction / summary
    latency: float       # 秒
    score: float         # 评分
    success: bool
    error: str = ""
    cost: float = 0.0
    tokens_used: int = 0
    created_at: int = 0


class ModelRouter:
    """
    模型路由器
    1. 管理多个模型配置
    2. 根据性能自动路由
    3. 故障时自动降级
    4. 成本优化
    """

    # 模型配置预设
    PRESET_MODELS = [
        ModelConfig(
            id="local_gemma",
            name="Gemma 3 4B (本地)",
            model_type=ModelType.LOCAL,
            provider="ollama",
            model_name="gemma3:4b",
            avg_latency=30.0,
            avg_score=72.0,
            success_rate=0.70,
            cost_per_1k=0.0,
            priority=1,
        ),
        ModelConfig(
            id="rule_engine",
            name="规则引擎 (本地)",
            model_type=ModelType.RULE,
            provider="builtin",
            model_name="rule_v1",
            avg_latency=0.1,
            avg_score=65.0,
            success_rate=0.62,
            cost_per_1k=0.0,
            priority=2,
        ),
        ModelConfig(
            id="cloud_openai",
            name="GPT-4o (云端)",
            model_type=ModelType.CLOUD,
            provider="openai",
            model_name="gpt-4o",
            avg_latency=5.0,
            avg_score=85.0,
            success_rate=0.78,
            cost_per_1k=0.005,
            priority=3,
        ),
        ModelConfig(
            id="cloud_anthropic",
            name="Claude 3.5 (云端)",
            model_type=ModelType.CLOUD,
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            avg_latency=6.0,
            avg_score=88.0,
            success_rate=0.80,
            cost_per_1k=0.003,
            priority=4,
        ),
    ]

    def __init__(self, db_path: str = None):
        if db_path is None:
            import os
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base, "data", "model_router.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._active_model: Optional[ModelConfig] = None
        self._failure_count: Dict[str, int] = {}  # model_id -> consecutive failures
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
            CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                model_type TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                avg_latency REAL DEFAULT 30.0,
                avg_score REAL DEFAULT 70.0,
                success_rate REAL DEFAULT 0.7,
                cost_per_1k REAL DEFAULT 0.0,
                is_active INTEGER DEFAULT 1,
                priority INTEGER DEFAULT 0,
                consecutive_failures INTEGER DEFAULT 0,
                last_failure_at INTEGER DEFAULT 0,
                last_success_at INTEGER DEFAULT 0
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS model_calls (
                id TEXT PRIMARY KEY,
                model_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                symbol TEXT,
                call_type TEXT,
                latency REAL,
                score REAL,
                success INTEGER,
                error TEXT DEFAULT '',
                cost REAL DEFAULT 0.0,
                tokens_used INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(model_id) REFERENCES models(id)
            )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_calls_model ON model_calls(model_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_calls_created ON model_calls(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_calls_success ON model_calls(success)")

        conn.commit()

        # 插入预设模型
        self._insert_preset_models()
        logger.info(f"模型路由器初始化: {self.db_path}")

    def _insert_preset_models(self):
        conn = self._get_conn()
        c = conn.cursor()
        for m in self.PRESET_MODELS:
            c.execute("SELECT id FROM models WHERE id = ?", (m.id,))
            if not c.fetchone():
                c.execute("""
                    INSERT INTO models (id, name, model_type, provider, model_name,
                        avg_latency, avg_score, success_rate, cost_per_1k, priority)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (m.id, m.name, m.model_type.value, m.provider, m.model_name,
                      m.avg_latency, m.avg_score, m.success_rate, m.cost_per_1k, m.priority))
        conn.commit()

    def select_model(
        self,
        urgency: str = "normal",  # fast / normal / best
        budget: str = "low",       # free / low / high
        symbol: str = "BTC",
    ) -> ModelConfig:
        """
        选择最佳模型
        urgency: fast(优先速度) / normal(平衡) / best(优先质量)
        budget: free(仅本地) / low(优先免费) / high(可以付费)
        """
        conn = self._get_conn()
        c = conn.cursor()

        # 过滤可用模型
        now = int(time.time())
        cooldown = 300  # 5分钟冷却期

        c.execute("""
            SELECT * FROM models
            WHERE is_active = 1
              AND (consecutive_failures < 3 OR last_failure_at < ?)
            ORDER BY priority ASC
        """, (now - cooldown,))

        rows = c.fetchall()
        if not rows:
            # 所有模型都故障，返回规则引擎
            return self._row_to_model(dict(rows[0])) if rows else ModelConfig(
                id="emergency", name="规则引擎", model_type=ModelType.RULE,
                provider="builtin", model_name="rule_v1",
                avg_latency=0.1, avg_score=65.0, success_rate=0.62, cost_per_1k=0.0
            )

        candidates = [self._row_to_model(dict(r)) for r in rows]

        # 预算过滤
        if budget == "free":
            candidates = [m for m in candidates if m.cost_per_1k == 0]
        elif budget == "low":
            candidates = [m for m in candidates if m.cost_per_1k < 0.001]

        # 速度优先
        if urgency == "fast":
            candidates.sort(key=lambda m: m.avg_latency)
        # 质量优先
        elif urgency == "best":
            candidates.sort(key=lambda m: -m.avg_score)

        return candidates[0] if candidates else candidates[0]

    def _row_to_model(self, row: dict) -> ModelConfig:
        return ModelConfig(
            id=row["id"],
            name=row["name"],
            model_type=ModelType(row["model_type"]),
            provider=row["provider"],
            model_name=row["model_name"],
            avg_latency=row["avg_latency"],
            avg_score=row["avg_score"],
            success_rate=row["success_rate"],
            cost_per_1k=row["cost_per_1k"],
            priority=row["priority"],
        )

    def record_call(
        self,
        model_id: str,
        model_name: str,
        symbol: str,
        call_type: str,
        latency: float,
        success: bool,
        score: float = 0.0,
        error: str = "",
        tokens_used: int = 0,
    ) -> str:
        """记录模型调用"""
        conn = self._get_conn()
        c = conn.cursor()

        call_id = hashlib.sha1(f"{model_id}{time.time()}".encode()).hexdigest()[:16]
        now = int(time.time())

        # 获取模型成本
        c.execute("SELECT cost_per_1k FROM models WHERE id = ?", (model_id,))
        row = c.fetchone()
        cost_per_1k = dict(row)["cost_per_1k"] if row else 0
        cost = tokens_used / 1000 * cost_per_1k

        c.execute("""
            INSERT INTO model_calls
            (id, model_id, model_name, symbol, call_type, latency, score, success, error, cost, tokens_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (call_id, model_id, model_name, symbol, call_type, latency, score,
              1 if success else 0, error, cost, tokens_used, now))

        # 更新模型统计
        c.execute("""
            UPDATE models SET
                avg_latency = (avg_latency * total_calls + ?) / (total_calls + 1),
                avg_score = (avg_score * total_calls + ?) / (total_calls + 1),
                last_success_at = CASE WHEN ? = 1 THEN ? ELSE last_success_at END,
                consecutive_failures = CASE WHEN ? = 0 THEN consecutive_failures + 1 ELSE 0 END,
                last_failure_at = CASE WHEN ? = 0 THEN ? ELSE last_failure_at END
            WHERE id = ?
        """, (latency, score, 1 if success else 0, now,
              1 if success else 0, 1 if success else 0, now, model_id))

        # 统计调用次数
        c.execute("""
            UPDATE models SET
                avg_latency = (SELECT AVG(latency) FROM model_calls WHERE model_id = ? AND created_at > ?),
                avg_score = (SELECT AVG(score) FROM model_calls WHERE model_id = ? AND created_at > ?),
                success_rate = (SELECT SUM(success)*1.0/COUNT(*) FROM model_calls WHERE model_id = ? AND created_at > ?)
            WHERE id = ?
        """, (model_id, now - 86400, model_id, now - 86400, model_id, now - 86400, model_id))

        # 连续失败超过5次则禁用
        c.execute("SELECT consecutive_failures FROM models WHERE id = ?", (model_id,))
        fail_row = c.fetchone()
        if fail_row and dict(fail_row)["consecutive_failures"] >= 5:
            c.execute("UPDATE models SET is_active = 0 WHERE id = ?", (model_id,))
            logger.warning(f"模型 {model_id} 连续失败5次，已自动禁用")

        conn.commit()
        return call_id

    def should_switch_model(self, current_model_id: str) -> Tuple[bool, str, str]:
        """
        判断是否需要切换模型
        返回: (should_switch, new_model_id, reason)
        """
        conn = self._get_conn()
        c = conn.cursor()

        # 检查当前模型表现
        c.execute("""
            SELECT * FROM models WHERE id = ?
        """, (current_model_id,))
        row = c.fetchone()
        if not row:
            return True, "rule_engine", "当前模型不存在"

        current = dict(row)

        # 连续失败过多
        if current["consecutive_failures"] >= 3:
            return True, "切换到备用模型", f"连续失败{current['consecutive_failures']}次"

        # 最近24小时表现下滑
        cutoff = int(time.time()) - 86400
        c.execute("""
            SELECT
                SUM(success)*1.0/COUNT(*) as recent_rate,
                AVG(score) as recent_score,
                COUNT(*) as recent_calls
            FROM model_calls
            WHERE model_id = ? AND created_at > ?
        """, (current_model_id, cutoff))
        recent = c.fetchone()

        if recent:
            recent_dict = dict(recent)
            if recent_dict["recent_calls"] >= 5:
                # 近期准确率下降超过15%
                if recent_dict["recent_rate"] < current["success_rate"] - 0.15:
                    return True, "rule_engine", f"准确率从{current['success_rate']*100:.0f}%降至{recent_dict['recent_rate']*100:.0f}%"
                # 延迟急剧上升
                c.execute("""
                    SELECT AVG(latency) as recent_latency FROM model_calls
                    WHERE model_id = ? AND created_at > ?
                """, (current_model_id, cutoff))
                lat_row = c.fetchone()
                if lat_row and dict(lat_row)["recent_latency"]:
                    recent_lat = dict(lat_row)["recent_latency"]
                    if recent_lat > current["avg_latency"] * 2:
                        return True, "rule_engine", f"延迟从{current['avg_latency']:.1f}s升至{recent_lat:.1f}s"

        return False, current_model_id, "当前模型表现正常"

    def get_model_comparison(self, days: int = 7) -> Dict:
        """各模型对比"""
        conn = self._get_conn()
        c = conn.cursor()

        cutoff = int(time.time()) - days * 86400

        c.execute("""
            SELECT
                m.id, m.name, m.model_type, m.provider,
                m.avg_latency, m.avg_score, m.success_rate,
                m.cost_per_1k, m.is_active, m.consecutive_failures,
                COUNT(c.id) as total_calls,
                SUM(CASE WHEN c.success = 1 THEN 1 ELSE 0 END) as successes,
                SUM(c.cost) as total_cost,
                SUM(c.tokens_used) as total_tokens,
                AVG(c.latency) as actual_latency,
                AVG(c.score) as actual_score
            FROM models m
            LEFT JOIN model_calls c ON m.id = c.model_id AND c.created_at > ?
            GROUP BY m.id
            ORDER BY m.priority
        """, (cutoff,))

        models = []
        for row in c.fetchall():
            d = dict(row)
            total = d["total_calls"] or 0
            successes = d["successes"] or 0
            actual_rate = successes / total if total > 0 else 0

            models.append({
                "id": d["id"],
                "name": d["name"],
                "type": d["model_type"],
                "provider": d["provider"],
                "is_active": bool(d["is_active"]),
                "consecutive_failures": d["consecutive_failures"],
                "calls_7d": total,
                "actual_latency": round(d["actual_latency"] or 0, 2),
                "actual_score": round(d["actual_score"] or 0, 1),
                "actual_success_rate": round(actual_rate * 100, 1),
                "total_cost_7d": round(d["total_cost"] or 0, 4),
                "total_tokens_7d": d["total_tokens"] or 0,
            })

        return {"models": models, "period_days": days}

    def get_best_model(self, metric: str = "score") -> Dict:
        """获取最佳模型"""
        conn = self._get_conn()
        c = conn.cursor()

        metric_map = {
            "latency": "avg_latency ASC",
            "score": "avg_score DESC",
            "success": "success_rate DESC",
        }

        order = metric_map.get(metric, "avg_score DESC")
        c.execute(f"SELECT * FROM models WHERE is_active = 1 ORDER BY {order} LIMIT 1")
        row = c.fetchone()
        if not row:
            return {}

        d = dict(row)
        return {
            "id": d["id"],
            "name": d["name"],
            "type": d["model_type"],
            "latency": round(d["avg_latency"], 2),
            "score": round(d["avg_score"], 1),
            "success_rate": round(d["success_rate"] * 100, 1),
        }


    def tune_model_params(self, model_id: str, adjustments: dict) -> dict:
        """调整模型参数（温度/top_p等）"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute('SELECT params FROM models WHERE id = ?', (model_id,))
        row = c.fetchone()
        if not row:
            return {'error': f'Model {model_id} not found'}
        import json
        params = json.loads(row[0]) if row[0] else {}
        params.update(adjustments)
        c.execute('UPDATE models SET params = ? WHERE id = ?',
                  (json.dumps(params, ensure_ascii=False), model_id))
        conn.commit()
        logger.info(f'Model {model_id} params updated: {adjustments}')
        return {'model_id': model_id, 'updated_params': params}

    def get_tuning_suggestions(self, model_id: str) -> list:
        """根据历史表现给出参数调优建议"""
        import time as _t
        try:
            conn = self._get_conn()
            c = conn.cursor()
            cutoff = int(_t.time()) - 86400 * 7
            c.execute(
                'SELECT success, latency_ms FROM model_usage WHERE model_id = ? AND created_at > ?',
                (model_id, cutoff))
            rows = c.fetchall()
        except Exception:
            return [{'suggestion': 'Insufficient data (table not found)', 'priority': 'low'}]
        if not rows:
            return [{'suggestion': 'Insufficient data', 'priority': 'low'}]
        success_rate = sum(1 for r in rows if r[0]) / len(rows)
        avg_latency = sum(r[1] for r in rows) / len(rows)
        suggestions = []
        if success_rate < 0.5:
            suggestions.append({'suggestion': 'Lower temperature for determinism', 'param': 'temperature', 'value': 0.3, 'priority': 'high'})
        if avg_latency > 30000:
            suggestions.append({'suggestion': 'Reduce max_tokens for speed', 'param': 'max_tokens', 'value': 512, 'priority': 'medium'})
        if success_rate > 0.8 and avg_latency < 10000:
            suggestions.append({'suggestion': 'Can increase temperature for diversity', 'param': 'temperature', 'value': 0.7, 'priority': 'low'})
        return suggestions or [{'suggestion': 'Current params performing well', 'priority': 'none'}]

    @safe_execute(default=None)
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
