"""
数据生命周期管理器
管理数据从采集到归档到清理的完整生命周期
"""
import sqlite3
import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from core.utils.logger import logger
from core.utils.helpers import safe_execute


@dataclass
class LifecycleStage:
    """数据生命周期阶段"""
    name: str
    duration_days: int
    compression: str
    storage_class: str  # hot/warm/cold/archive


class DataLifecycleManager:
    """
    数据生命周期管理器
    
    生命周期阶段：
    HOT    -> 最近N天，常驻内存，高频访问
    WARM   -> 中期数据，磁盘缓存，低频访问
    COLD   -> 长期数据，压缩存储，按需加载
    ARCHIVE -> 历史数据，归档压缩，极少访问
    DELETE -> 超出保留期，安全删除
    """
    
    STAGES = {
        'hot': {
            'description': '热数据 - 常驻内存',
            'max_age_days': 3,
            'storage': 'memory',
            'compression': 'none',
        },
        'warm': {
            'description': '温数据 - 磁盘缓存',
            'max_age_days': 30,
            'storage': 'disk',
            'compression': 'none',
        },
        'cold': {
            'description': '冷数据 - 压缩存储',
            'max_age_days': 180,
            'storage': 'compressed_disk',
            'compression': 'gzip',
        },
        'archive': {
            'description': '归档数据 - 长期保存',
            'max_age_days': 730,
            'storage': 'archive',
            'compression': 'gzip',
        },
    }
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            from config.settings import DATA_DIR
            db_path = os.path.join(DATA_DIR, "lifecycle.db")
        self.db_path = db_path
        self._registry: Dict[str, Dict] = {}
        self._init_db()
        self._load_registry()
    
    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS data_registry (
                category TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL,
                total_rows INTEGER DEFAULT 0,
                total_mb REAL DEFAULT 0,
                current_stage TEXT DEFAULT 'hot',
                last_accessed INTEGER,
                last_compressed INTEGER,
                config TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS lifecycle_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                category TEXT NOT NULL,
                from_stage TEXT NOT NULL,
                to_stage TEXT NOT NULL,
                rows_affected INTEGER DEFAULT 0,
                mb_freed REAL DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()
    
    def _load_registry(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM data_registry')
        for row in c.fetchall():
            self._registry[row['category']] = dict(row)
        conn.close()
    
    @safe_execute(default={})
    def register(self, category: str, config: Dict = None):
        """注册数据类别"""
        if category not in self._registry:
            entry = {
                'category': category,
                'created_at': int(time.time()),
                'total_rows': 0,
                'total_mb': 0,
                'current_stage': 'hot',
                'last_accessed': int(time.time()),
                'last_compressed': 0,
                'config': json.dumps(config or {}, ensure_ascii=False)
            }
            self._registry[category] = entry
            self._save_registry_entry(entry)
            logger.info(f"数据类别已注册: {category}")
        return self._registry[category]
    
    @safe_execute(default=None)
    def get_stage(self, category: str) -> Optional[str]:
        """获取数据当前阶段"""
        if category in self._registry:
            return self._registry[category]['current_stage']
        return None
    
    @safe_execute(default={})
    async def promote(self, category: str):
        """数据晋升（从冷到热，被访问时触发）"""
        current = self.get_stage(category)
        if not current:
            return {}
        
        stages_order = ['archive', 'cold', 'warm', 'hot']
        current_idx = stages_order.index(current) if current in stages_order else 0
        
        self._registry[category]['current_stage'] = current
        self._registry[category]['last_accessed'] = int(time.time())
        self._save_registry_entry(self._registry[category])
        
        return self._registry[category]
    
    @safe_execute(default={})
    async def demote(self, category: str) -> Dict:
        """数据降级（从热到冷，定时任务触发）"""
        current = self.get_stage(category)
        if not current:
            return {}
        
        stages_order = ['hot', 'warm', 'cold', 'archive']
        current_idx = stages_order.index(current) if current in stages_order else 0
        
        if current_idx < len(stages_order) - 1:
            from_stage = current
            to_stage = stages_order[current_idx + 1]
            
            mb_freed = self._execute_demotion(category, from_stage, to_stage)
            
            self._registry[category]['current_stage'] = to_stage
            self._save_registry_entry(self._registry[category])
            self._log_event(category, from_stage, to_stage, mb_freed=mb_freed)
            
            logger.info(f"数据降级: {category} {from_stage} -> {to_stage}, 释放 {mb_freed:.2f}MB")
        
        return self._registry[category]
    
    def _execute_demotion(self, category: str, from_stage: str, to_stage: str) -> float:
        """执行数据降级操作"""
        mb_freed = 0
        
        if to_stage == 'warm':
            # 从内存缓存移到磁盘（如果是缓存数据）
            pass
        elif to_stage == 'cold':
            # 压缩数据
            mb_freed = self._compress_category(category)
        elif to_stage == 'archive':
            # 归档数据
            mb_freed = self._archive_category(category)
        
        return mb_freed
    
    @safe_execute(default=0)
    def _compress_category(self, category: str) -> float:
        """压缩数据类别"""
        # 简化实现
        return 0
    
    @safe_execute(default=0)
    def _archive_category(self, category: str) -> float:
        """归档数据类别"""
        from core.data.cleaner.intelligent_cleaner import get_cleaner
        # 实际应该将数据移到归档存储
        return 0
    
    @safe_execute(default=[])
    async def run_lifecycle_cycle(self) -> List[Dict]:
        """运行一个完整的生命周期管理周期"""
        results = []
        
        for category, info in list(self._registry.items()):
            current_stage = info['current_stage']
            stage_config = self.STAGES.get(current_stage, {})
            max_age = stage_config.get('max_age_days', 30)
            
            age_days = (time.time() - info['created_at']) / 86400
            
            if age_days > max_age:
                result = await self.demote(category)
                results.append({
                    'category': category,
                    'action': 'demoted',
                    'from': current_stage,
                    'to': result.get('current_stage', 'unknown'),
                    'age_days': round(age_days)
                })
        
        return results
    
    @safe_execute(default={})
    def get_lifecycle_summary(self) -> Dict:
        """获取生命周期管理摘要"""
        summary = {}
        for stage_name in ['hot', 'warm', 'cold', 'archive']:
            categories = [
                cat for cat, info in self._registry.items()
                if info['current_stage'] == stage_name
            ]
            summary[stage_name] = {
                'count': len(categories),
                'categories': categories,
                'description': self.STAGES[stage_name]['description']
            }
        return summary
    
    def _save_registry_entry(self, entry: Dict):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO data_registry 
            (category, created_at, total_rows, total_mb, current_stage, last_accessed, last_compressed, config)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry['category'], entry['created_at'], entry['total_rows'],
            entry['total_mb'], entry['current_stage'], entry['last_accessed'],
            entry['last_compressed'], entry.get('config', '{}')
        ))
        conn.commit()
        conn.close()
    
    def _log_event(self, category: str, from_stage: str, to_stage: str, rows: int = 0, mb_freed: float = 0):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO lifecycle_events (timestamp, category, from_stage, to_stage, rows_affected, mb_freed)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (int(time.time()), category, from_stage, to_stage, rows, mb_freed))
        conn.commit()
        conn.close()


_lifecycle_mgr: Optional[DataLifecycleManager] = None

def get_lifecycle_manager() -> DataLifecycleManager:
    global _lifecycle_mgr
    if _lifecycle_mgr is None:
        _lifecycle_mgr = DataLifecycleManager()
    return _lifecycle_mgr
