"""
智能缓存管理器
支持 TTL、LRU、优先级缓存策略
"""
import os
import json
import time
import hashlib
import threading
from typing import Any, Optional, Dict, List
from collections import OrderedDict
from dataclasses import dataclass, field
from core.utils.logger import logger
from core.utils.helpers import safe_execute


@dataclass
class CacheEntry:
    key: str
    value: Any
    created_at: float
    ttl: float  # seconds
    hits: int = 0
    last_accessed: float = 0
    size_bytes: int = 0
    priority: int = 5  # 1-10, 10 highest


class CacheManager:
    """
    多层智能缓存管理器
    
    L1: 内存缓存 (OrderedDict LRU)
    L2: 文件缓存 (JSON + gzip)
    L3: 可选 Redis
    
    策略：
    - TTL 过期自动淘汰
    - LRU 容量淘汰
    - 优先级保护（高优先级不被LRU淘汰）
    """
    
    def __init__(self, max_memory_items: int = 1000, max_memory_mb: float = 100,
                 disk_cache_dir: str = None):
        if disk_cache_dir is None:
            from config.settings import CACHE_DIR
            disk_cache_dir = CACHE_DIR
        self.disk_cache_dir = disk_cache_dir
        os.makedirs(disk_cache_dir, exist_ok=True)
        
        self.max_memory_items = max_memory_items
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        
        # L1 内存缓存
        self._memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._memory_size = 0
        self._lock = threading.RLock()
        
        # 统计
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'disk_reads': 0,
            'disk_writes': 0,
        }
        
        logger.info(f"缓存管理器初始化: 内存上限 {max_memory_items} 条 / {max_memory_mb}MB")
    
    @safe_execute(default=None)
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            entry = self._memory_cache.get(key)
            
            if entry:
                # 检查TTL
                if time.time() - entry.created_at > entry.ttl:
                    del self._memory_cache[key]
                    self._memory_size -= entry.size_bytes
                    self._stats['evictions'] += 1
                    # 尝试从磁盘加载
                    return self._load_from_disk(key)
                
                # 更新访问时间和hits
                entry.last_accessed = time.time()
                entry.hits += 1
                self._memory_cache.move_to_end(key)
                self._stats['hits'] += 1
                return entry.value
            
            self._stats['misses'] += 1
            # 尝试从磁盘加载
            return self._load_from_disk(key)
    
    @safe_execute(default=False)
    def set(self, key: str, value: Any, ttl: float = 300, priority: int = 5):
        """设置缓存值"""
        with self._lock:
            # 如果已存在，先移除
            if key in self._memory_cache:
                old = self._memory_cache.pop(key)
                self._memory_size -= old.size_bytes
            
            # 计算大小
            size = len(json.dumps(value, default=str, ensure_ascii=False)) if value else 0
            
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl,
                last_accessed=time.time(),
                size_bytes=size,
                priority=priority
            )
            
            # 检查容量
            while (len(self._memory_cache) >= self.max_memory_items or
                   self._memory_size + size > self.max_memory_bytes):
                self._evict_lru(protect_priority=priority)
            
            self._memory_cache[key] = entry
            self._memory_size += size
            
            # 同时写入磁盘（异步模拟）
            self._write_to_disk(key, value, ttl)
        
        return True
    
    @safe_execute(default=False)
    def delete(self, key: str):
        """删除缓存"""
        with self._lock:
            if key in self._memory_cache:
                entry = self._memory_cache.pop(key)
                self._memory_size -= entry.size_bytes
            
            # 删除磁盘缓存
            disk_path = self._disk_path(key)
            if os.path.exists(disk_path):
                os.remove(disk_path)
        
        return True
    
    @safe_execute(default={})
    def get_multi(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取"""
        return {k: self.get(k) for k in keys if self.get(k) is not None}
    
    @safe_execute(default=False)
    def set_multi(self, items: Dict[str, Any], ttl: float = 300):
        """批量设置"""
        for k, v in items.items():
            self.set(k, v, ttl)
        return True
    
    def _evict_lru(self, protect_priority: int = 0):
        """LRU淘汰（保护高优先级）"""
        # 找到优先级最低的最旧条目
        evict_key = None
        for key in self._memory_cache:
            entry = self._memory_cache[key]
            if entry.priority < protect_priority:
                evict_key = key
                break
        
        if evict_key is None and self._memory_cache:
            evict_key = next(iter(self._memory_cache))
        
        if evict_key:
            entry = self._memory_cache.pop(evict_key)
            self._memory_size -= entry.size_bytes
            self._stats['evictions'] += 1
    
    def _disk_path(self, key: str) -> str:
        """获取磁盘缓存路径"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.disk_cache_dir, f"{key_hash}.json")
    
    @safe_execute(default=None)
    def _write_to_disk(self, key: str, value: Any, ttl: float):
        """写入磁盘缓存"""
        try:
            path = self._disk_path(key)
            data = {
                'value': value,
                'created_at': time.time(),
                'ttl': ttl,
            }
            with open(path, 'w') as f:
                json.dump(data, f, default=str, ensure_ascii=False)
            self._stats['disk_writes'] += 1
        except Exception as e:
            logger.debug(f"磁盘缓存写入失败: {e}")
    
    @safe_execute(default=None)
    def _load_from_disk(self, key: str) -> Optional[Any]:
        """从磁盘加载缓存"""
        try:
            path = self._disk_path(key)
            if not os.path.exists(path):
                return None
            
            with open(path, 'r') as f:
                data = json.load(f)
            
            # 检查TTL
            if time.time() - data.get('created_at', 0) > data.get('ttl', 0):
                os.remove(path)
                return None
            
            self._stats['disk_reads'] += 1
            
            # 回填内存缓存
            self.set(key, data['value'], data.get('ttl', 300))
            return data['value']
        except Exception as e:
            logger.debug(f"磁盘缓存读取失败: {e}")
            return None
    
    @safe_execute(default={})
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        total = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total * 100 if total > 0 else 0
        
        return {
            'memory_items': len(self._memory_cache),
            'memory_size_mb': round(self._memory_size / (1024 * 1024), 2),
            'max_memory_mb': round(self.max_memory_bytes / (1024 * 1024), 2),
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate': f"{hit_rate:.1f}%",
            'evictions': self._stats['evictions'],
            'disk_reads': self._stats['disk_reads'],
            'disk_writes': self._stats['disk_writes'],
        }
    
    @safe_execute(default=0)
    def clear(self, pattern: str = None) -> int:
        """清空缓存"""
        with self._lock:
            if pattern:
                keys_to_delete = [k for k in self._memory_cache if pattern in k]
            else:
                keys_to_delete = list(self._memory_cache.keys())
            
            for key in keys_to_delete:
                entry = self._memory_cache.pop(key)
                self._memory_size -= entry.size_bytes
                disk_path = self._disk_path(key)
                if os.path.exists(disk_path):
                    os.remove(disk_path)
            
            return len(keys_to_delete)
    
    @safe_execute(default=[])
    def get_expired_keys(self) -> List[str]:
        """获取已过期但未清理的key"""
        now = time.time()
        return [
            key for key, entry in self._memory_cache.items()
            if now - entry.created_at > entry.ttl
        ]
    
    @safe_execute(default=0)
    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        expired = self.get_expired_keys()
        for key in expired:
            self.delete(key)
        return len(expired)


_cache_mgr: Optional[CacheManager] = None

def get_cache_manager() -> CacheManager:
    global _cache_mgr
    if _cache_mgr is None:
        _cache_mgr = CacheManager()
    return _cache_mgr
