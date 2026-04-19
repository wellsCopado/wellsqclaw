"""
智能数据清理模块 - IntelligentDataCleaner
基于使用频率、重要性、存储成本的三维清理策略
"""
import sqlite3
import gzip
import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from core.utils.logger import logger
from core.utils.helpers import safe_execute


@dataclass
class CleanupResult:
    category: str
    deleted_rows: int
    deleted_mb: float
    compressed_rows: int
    compressed_mb: float
    preserved_important: int


class IntelligentDataCleaner:
    """
    智能数据清理器
    
    策略原则：
    - 高频使用数据：保留较短时间
    - 低频但重要数据：保留较长时间
    - 重要性高的数据：延长保留时间
    """
    
    # 数据保留策略：基于数据类型和使用频率
    RETENTION_POLICIES = {
        # 高频使用数据：保留较短时间
        'spot_1m': {'days': 3, 'compression': 'hourly_after_1d'},
        'spot_5m': {'days': 7, 'compression': 'daily_after_3d'},
        'spot_15m': {'days': 14, 'compression': 'daily_after_7d'},
        'spot_1h': {'days': 30, 'compression': 'weekly_after_14d'},
        'spot_4h': {'days': 90, 'compression': 'monthly_after_30d'},
        
        # 低频但重要数据：保留较长时间
        'spot_1d': {'days': 365, 'compression': 'monthly_after_90d'},
        'spot_1w': {'days': 365 * 2, 'compression': 'quarterly_after_180d'},
        'spot_1M': {'days': 365 * 5, 'compression': 'yearly_after_365d'},
        
        # 衍生品数据
        'derivatives_funding': {'days': 30, 'compression': 'daily_after_7d'},
        'derivatives_oi': {'days': 90, 'compression': 'weekly_after_30d'},
        'derivatives_liquidations': {'days': 30, 'compression': 'daily_after_7d'},
        
        # 链上数据
        'onchain_transactions': {'days': 14, 'compression': 'daily_after_3d'},
        'onchain_addresses': {'days': 30, 'compression': 'weekly_after_7d'},
        'onchain_metrics': {'days': 180, 'compression': 'monthly_after_30d'},
        
        # 新闻数据
        'news_raw': {'days': 7, 'compression': 'none'},
        'news_analysis': {'days': 90, 'compression': 'weekly_after_14d'},
        
        # AI分析结果
        'ai_analysis': {'days': 180, 'compression': 'monthly_after_30d'},
        'ai_predictions': {'days': 365, 'compression': 'quarterly_after_90d'},
        
        # 回归验证和知识库数据
        'regression_results': {'days': 365 * 2, 'compression': 'yearly_after_365d'},
        'knowledge_base': {'days': 365 * 5, 'compression': 'yearly_after_730d'},
    }
    
    # 数据重要性评分规则
    IMPORTANCE_RULES = {
        'price_anomaly': 0.9,      # 价格异常
        'large_transfer': 0.8,     # 大额转账
        'regulatory_news': 0.85,   # 监管新闻
        'technical_break': 0.7,    # 技术突破
        'ai_high_confidence': 0.8, # AI高置信度分析
    }
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            from config.settings import DATA_DIR
            db_path = os.path.join(DATA_DIR, "cleanup.db")
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化清理记录数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS cleanup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                category TEXT NOT NULL,
                deleted_rows INTEGER DEFAULT 0,
                deleted_mb REAL DEFAULT 0,
                compressed_rows INTEGER DEFAULT 0,
                compressed_mb REAL DEFAULT 0,
                importance_score REAL DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()
    
    @safe_execute(default={})
    async def intelligent_cleanup(self) -> Dict:
        """执行智能清理"""
        cleanup_report = {
            'timestamp': int(time.time()),
            'total_deleted_mb': 0,
            'total_compressed_mb': 0,
            'by_category': {},
            'importance_preserved': []
        }
        
        for category, policy in self.RETENTION_POLICIES.items():
            try:
                # 1. 计算数据重要性
                importance_score = await self.calculate_importance(category)
                
                # 2. 如果重要性高，延长保留时间
                adjusted_policy = self.adjust_policy_by_importance(policy, importance_score)
                
                # 3. 执行清理或压缩
                result = await self.process_category(category, adjusted_policy)
                
                cleanup_report['by_category'][category] = result
                cleanup_report['total_deleted_mb'] += result.get('deleted_mb', 0)
                cleanup_report['total_compressed_mb'] += result.get('compressed_mb', 0)
                
                if importance_score > 0.7:
                    cleanup_report['importance_preserved'].append({
                        'category': category,
                        'score': importance_score
                    })
                
                # 记录清理历史
                self._log_cleanup(category, result, importance_score)
                
            except Exception as e:
                logger.error(f"清理 {category} 失败: {e}")
        
        logger.info(f"智能清理完成: 删除 {cleanup_report['total_deleted_mb']:.2f}MB, "
                   f"压缩 {cleanup_report['total_compressed_mb']:.2f}MB")
        return cleanup_report
    
    @safe_execute(default=0.5)
    async def calculate_importance(self, category: str) -> float:
        """计算数据重要性分数"""
        # 基于使用频率、预测价值、独特性计算重要性
        usage_freq = await self.get_usage_frequency(category)
        prediction_value = await self.get_prediction_value(category)
        uniqueness = await self.get_uniqueness(category)
        
        # 加权计算重要性分数
        importance = (
            usage_freq * 0.4 +
            prediction_value * 0.4 +
            uniqueness * 0.2
        )
        
        return min(max(importance, 0), 1)  # 限制在0-1之间
    
    @safe_execute(default=0.5)
    async def get_usage_frequency(self, category: str) -> float:
        """获取数据使用频率"""
        # 从查询日志统计
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 最近7天的查询次数
        week_ago = int(time.time()) - 7 * 86400
        c.execute('''
            SELECT COUNT(*) FROM cleanup_history 
            WHERE category = ? AND timestamp > ?
        ''', (category, week_ago))
        
        count = c.fetchone()[0]
        conn.close()
        
        # 归一化到0-1
        return min(count / 100, 1.0)
    
    @safe_execute(default=0.5)
    async def get_prediction_value(self, category: str) -> float:
        """获取数据预测价值"""
        # 基于历史预测准确率评估
        if 'ai_' in category or 'prediction' in category:
            return 0.9
        elif 'spot_' in category:
            return 0.8
        elif 'derivatives_' in category:
            return 0.7
        elif 'onchain_' in category:
            return 0.6
        return 0.5
    
    @safe_execute(default=0.5)
    async def get_uniqueness(self, category: str) -> float:
        """获取数据独特性"""
        # 难以从其他数据源获取的数据独特性更高
        if 'knowledge' in category or 'regression' in category:
            return 1.0
        elif 'onchain_' in category:
            return 0.8
        elif 'news_' in category:
            return 0.7
        return 0.5
    
    def adjust_policy_by_importance(self, policy: Dict, importance: float) -> Dict:
        """根据重要性调整保留策略"""
        adjusted = policy.copy()
        
        # 重要性高则延长保留时间
        if importance > 0.8:
            adjusted['days'] = int(policy['days'] * 1.5)
        elif importance > 0.6:
            adjusted['days'] = int(policy['days'] * 1.2)
        elif importance < 0.3:
            adjusted['days'] = int(policy['days'] * 0.8)
        
        return adjusted
    
    @safe_execute(default={})
    async def process_category(self, category: str, policy: Dict) -> Dict:
        """处理特定类别的数据"""
        cutoff_date = datetime.now() - timedelta(days=policy['days'])
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        result = {
            'deleted_mb': 0,
            'compressed_mb': 0,
            'deleted_rows': 0,
            'compressed_rows': 0,
            'cutoff_date': cutoff_date.isoformat()
        }
        
        if policy.get('compression') != 'none':
            # 先压缩，再清理
            compressed = await self.compress_data(category, cutoff_timestamp, policy['compression'])
            result['compressed_mb'] = compressed.get('mb', 0)
            result['compressed_rows'] = compressed.get('rows', 0)
        
        # 执行清理
        deleted = await self.delete_data(category, cutoff_timestamp)
        result['deleted_mb'] = deleted.get('mb', 0)
        result['deleted_rows'] = deleted.get('rows', 0)
        
        return result
    
    @safe_execute(default={'mb': 0, 'rows': 0})
    async def compress_data(self, category: str, cutoff: int, strategy: str) -> Dict:
        """压缩旧数据"""
        # 简化实现：将数据导出为gzip压缩的JSON
        result = {'mb': 0, 'rows': 0}
        
        # 获取旧数据
        from core.data.storage import get_storage
        storage = get_storage()
        
        old_data = storage.get_data_before(category, cutoff)
        if not old_data:
            return result
        
        # 压缩存储
        archive_dir = os.path.join(os.path.dirname(self.db_path), "archives")
        os.makedirs(archive_dir, exist_ok=True)
        
        archive_file = os.path.join(archive_dir, f"{category}_{cutoff}.json.gz")
        
        with gzip.open(archive_file, 'wt', encoding='utf-8') as f:
            json.dump(old_data, f)
        
        file_size = os.path.getsize(archive_file) / (1024 * 1024)  # MB
        result['mb'] = file_size
        result['rows'] = len(old_data)
        
        logger.info(f"压缩 {category}: {len(old_data)} 条记录 -> {file_size:.2f}MB")
        return result
    
    @safe_execute(default={'mb': 0, 'rows': 0})
    async def delete_data(self, category: str, cutoff: int) -> Dict:
        """删除过期数据"""
        result = {'mb': 0, 'rows': 0}
        
        from core.data.storage import get_storage
        storage = get_storage()
        
        deleted = storage.delete_data_before(category, cutoff)
        result['rows'] = deleted.get('rows', 0)
        result['mb'] = deleted.get('mb', 0)
        
        logger.info(f"删除 {category}: {result['rows']} 条记录")
        return result
    
    def _log_cleanup(self, category: str, result: Dict, importance: float):
        """记录清理历史"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO cleanup_history 
            (timestamp, category, deleted_rows, deleted_mb, compressed_rows, compressed_mb, importance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            int(time.time()),
            category,
            result.get('deleted_rows', 0),
            result.get('deleted_mb', 0),
            result.get('compressed_rows', 0),
            result.get('compressed_mb', 0),
            importance
        ))
        conn.commit()
        conn.close()
    
    @safe_execute(default=[])
    def get_cleanup_history(self, days: int = 30) -> List[Dict]:
        """获取清理历史"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        cutoff = int(time.time()) - days * 86400
        c.execute('''
            SELECT * FROM cleanup_history 
            WHERE timestamp > ? 
            ORDER BY timestamp DESC
        ''', (cutoff,))
        
        rows = c.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]


# 全局单例
_cleaner: Optional[IntelligentDataCleaner] = None

def get_cleaner() -> IntelligentDataCleaner:
    global _cleaner
    if _cleaner is None:
        _cleaner = IntelligentDataCleaner()
    return _cleaner
