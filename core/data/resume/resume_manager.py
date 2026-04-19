"""
断点续传管理器
支持数据采集和分析任务的断点续传
"""
import sqlite3
import os
import time
import json
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from core.utils.logger import logger
from core.utils.helpers import safe_execute


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RESUMED = "resumed"


@dataclass
class ResumeCheckpoint:
    """续传检查点"""
    task_id: str
    task_type: str
    status: str
    progress: float  # 0-100
    checkpoint_data: Dict
    created_at: float
    updated_at: float
    error: str = ""
    retry_count: int = 0


class ResumeManager:
    """
    断点续传管理器
    
    功能：
    1. 任务状态持久化
    2. 断点检查点保存与恢复
    3. 失败自动重试
    4. 任务恢复时间 < 10分钟
    """
    
    MAX_RETRY = 3
    RESUME_TIMEOUT = 600  # 10分钟
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            from config.settings import DATA_DIR
            db_path = os.path.join(DATA_DIR, "resume.db")
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                progress REAL DEFAULT 0,
                checkpoint_data TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                error TEXT DEFAULT '',
                retry_count INTEGER DEFAULT 0
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_task_status ON tasks(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_task_type ON tasks(task_type)')
        conn.commit()
        conn.close()
    
    @safe_execute(default="")
    def create_task(self, task_type: str, initial_data: Dict = None) -> str:
        """创建新任务"""
        task_id = f"{task_type}_{int(time.time())}_{id(self) % 10000}"
        now = int(time.time())
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO tasks (task_id, task_type, status, progress, checkpoint_data, created_at, updated_at)
            VALUES (?, ?, 'pending', 0, ?, ?, ?)
        ''', (task_id, task_type, json.dumps(initial_data or {}), now, now))
        conn.commit()
        conn.close()
        
        logger.info(f"任务创建: {task_id} ({task_type})")
        return task_id
    
    @safe_execute(default=False)
    def save_checkpoint(self, task_id: str, progress: float, data: Dict = None):
        """保存检查点"""
        now = int(time.time())
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            UPDATE tasks SET progress = ?, checkpoint_data = ?, updated_at = ?, status = 'running'
            WHERE task_id = ?
        ''', (progress, json.dumps(data or {}, ensure_ascii=False), now, task_id))
        conn.commit()
        conn.close()
    
    @safe_execute(default=None)
    def get_checkpoint(self, task_id: str) -> Optional[ResumeCheckpoint]:
        """获取检查点"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return ResumeCheckpoint(
            task_id=row['task_id'],
            task_type=row['task_type'],
            status=row['status'],
            progress=row['progress'],
            checkpoint_data=json.loads(row['checkpoint_data'] or '{}'),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            error=row['error'],
            retry_count=row['retry_count'],
        )
    
    @safe_execute(default=False)
    def complete_task(self, task_id: str):
        """标记任务完成"""
        now = int(time.time())
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            UPDATE tasks SET status = 'completed', progress = 100, updated_at = ?
            WHERE task_id = ?
        ''', (now, task_id))
        conn.commit()
        conn.close()
        logger.info(f"任务完成: {task_id}")
    
    @safe_execute(default=False)
    def fail_task(self, task_id: str, error: str):
        """标记任务失败"""
        now = int(time.time())
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 获取当前重试次数
        c.execute('SELECT retry_count FROM tasks WHERE task_id = ?', (task_id,))
        row = c.fetchone()
        retry_count = row[0] + 1 if row else 0
        
        if retry_count < self.MAX_RETRY:
            # 自动重试
            c.execute('''
                UPDATE tasks SET status = 'pending', error = ?, retry_count = ?, updated_at = ?
                WHERE task_id = ?
            ''', (error, retry_count, now, task_id))
            logger.warning(f"任务失败(将重试 {retry_count}/{self.MAX_RETRY}): {task_id} - {error}")
        else:
            # 超过重试次数
            c.execute('''
                UPDATE tasks SET status = 'failed', error = ?, retry_count = ?, updated_at = ?
                WHERE task_id = ?
            ''', (error, retry_count, now, task_id))
            logger.error(f"任务永久失败: {task_id} - {error}")
        
        conn.commit()
        conn.close()
    
    @safe_execute(default=False)
    def pause_task(self, task_id: str):
        """暂停任务"""
        now = int(time.time())
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE tasks SET status = 'paused', updated_at = ? WHERE task_id = ?", (now, task_id))
        conn.commit()
        conn.close()
    
    @safe_execute(default=None)
    async def resume_task(self, task_id: str) -> Optional[Dict]:
        """恢复任务"""
        checkpoint = self.get_checkpoint(task_id)
        if not checkpoint:
            return None
        
        # 检查恢复超时
        age = time.time() - checkpoint.updated_at
        if age > self.RESUME_TIMEOUT:
            logger.warning(f"任务 {task_id} 续传超时 (上次更新 {age:.0f}s 前)")
            return None
        
        # 标记为恢复状态
        now = int(time.time())
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE tasks SET status = 'resumed', updated_at = ? WHERE task_id = ?", (now, task_id))
        conn.commit()
        conn.close()
        
        logger.info(f"任务恢复: {task_id} (进度 {checkpoint.progress:.1f}%)")
        
        return {
            'task_id': task_id,
            'task_type': checkpoint.task_type,
            'progress': checkpoint.progress,
            'checkpoint_data': checkpoint.checkpoint_data,
        }
    
    @safe_execute(default=[])
    def get_pending_tasks(self, task_type: str = None) -> List[Dict]:
        """获取待恢复的任务"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        if task_type:
            c.execute("SELECT * FROM tasks WHERE status IN ('pending', 'paused', 'resumed') AND task_type = ? ORDER BY updated_at DESC", (task_type,))
        else:
            c.execute("SELECT * FROM tasks WHERE status IN ('pending', 'paused', 'resumed') ORDER BY updated_at DESC")
        
        rows = c.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    @safe_execute(default=[])
    def get_all_tasks(self, limit: int = 50) -> List[Dict]:
        """获取所有任务"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @safe_execute(default=0)
    def cleanup_old_tasks(self, days: int = 7) -> int:
        """清理旧任务记录"""
        cutoff = int(time.time()) - days * 86400
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM tasks WHERE status = 'completed' AND updated_at < ?", (cutoff,))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        return deleted


_resume_mgr: Optional[ResumeManager] = None

def get_resume_manager() -> ResumeManager:
    global _resume_mgr
    if _resume_mgr is None:
        _resume_mgr = ResumeManager()
    return _resume_mgr
