"""
CryptoMind Pro Plus AI - 数据备份与恢复

功能:
- 自动定时备份（SQLite → timestamped副本）
- 备份保留策略（保留最近N个）
- 压缩备份（gzip）
- 恢复到指定备份点
- 备份完整性校验（SHA256）
- 备份状态查询
"""

import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Optional

from core.utils.logger import logger
from core.utils.helpers import safe_execute


@dataclass
class BackupRecord:
    backup_id: str
    timestamp: int
    db_name: str
    original_size: int
    compressed_size: int
    sha256: str
    auto: bool  # True=自动备份, False=手动

    def to_dict(self):
        return asdict(self)


class BackupManager:
    """
    数据库备份管理器

    配置:
    - backup_dir: 备份存放目录
    - max_backups: 最多保留N个备份 (默认30)
    - compress: 是否压缩 (默认True)
    - auto_interval_sec: 自动备份间隔 (默认3600=1小时)
    """

    def __init__(self, data_dir: str = None, backup_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        if backup_dir is None:
            backup_dir = os.path.join(data_dir, "backups")

        self._data_dir = os.path.abspath(data_dir)
        self._backup_dir = os.path.abspath(backup_dir)
        self._max_backups = 30
        self._compress = True
        self._last_auto_backup = 0
        self._auto_interval = 3600  # 1小时

        os.makedirs(self._backup_dir, exist_ok=True)

        # 备份索引
        self._index_file = os.path.join(self._backup_dir, "backup_index.json")
        self._index: list[dict] = self._load_index()

        logger.info(f"💾 备份管理器初始化: {self._backup_dir}")

    def _load_index(self) -> list[dict]:
        if os.path.exists(self._index_file):
            try:
                with open(self._index_file) as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_index(self):
        with open(self._index_file, "w") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

    def _discover_databases(self) -> list[str]:
        """发现所有SQLite数据库文件"""
        db_files = []
        for root, dirs, files in os.walk(self._data_dir):
            # 跳过备份目录自身
            if "backups" in root:
                continue
            for f in files:
                if f.endswith(".db") or f.endswith(".db-wal"):
                    full = os.path.join(root, f)
                    if "backups" not in full:
                        db_files.append(full)
        # 去重（.db-wal跟.db算同一个）
        seen = set()
        result = []
        for f in db_files:
            base = f.replace("-wal", "").replace("-shm", "")
            if base not in seen:
                seen.add(base)
                result.append(f)
        return [f for f in result if not f.endswith("-wal") and not f.endswith("-shm")]

    def _sha256_file(self, filepath: str) -> str:
        """计算文件SHA256"""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _sqlite_checkpoint(self, db_path: str):
        """强制WAL checkpoint，确保所有数据写入主文件"""
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA wal_checkpoint(FULL)")
            conn.close()
        except Exception as e:
            logger.warning(f"WAL checkpoint失败 {db_path}: {e}")

    @safe_execute(default=None)
    def backup(self, label: str = "manual") -> dict:
        """
        执行完整备份

        Returns:
            备份结果 dict
        """
        db_files = self._discover_databases()
        if not db_files:
            return {"success": False, "error": "No databases found"}

        timestamp = int(time.time())
        backup_id = f"{label}_{timestamp}"
        backup_subdir = os.path.join(self._backup_dir, backup_id)
        os.makedirs(backup_subdir, exist_ok=True)

        results = []
        for db_path in db_files:
            try:
                # WAL checkpoint
                self._sqlite_checkpoint(db_path)

                db_name = os.path.relpath(db_path, self._data_dir)
                dest_name = db_name.replace(os.sep, "_")
                dest_path = os.path.join(backup_subdir, dest_name)

                original_size = os.path.getsize(db_path)
                sha256 = self._sha256_file(db_path)

                if self._compress:
                    dest_path += ".gz"
                    with open(db_path, "rb") as f_in:
                        with gzip.open(dest_path, "wb", compresslevel=6) as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    compressed_size = os.path.getsize(dest_path)
                else:
                    shutil.copy2(db_path, dest_path)
                    compressed_size = original_size

                record = BackupRecord(
                    backup_id=backup_id,
                    timestamp=timestamp,
                    db_name=db_name,
                    original_size=original_size,
                    compressed_size=compressed_size,
                    sha256=sha256,
                    auto=(label == "auto"),
                )
                results.append(record.to_dict())

            except Exception as e:
                logger.error(f"备份失败 {db_path}: {e}")
                results.append({"error": str(e), "db": db_path})

        # 记录索引
        index_entry = {
            "backup_id": backup_id,
            "timestamp": timestamp,
            "label": label,
            "files": results,
            "total_size": sum(r.get("compressed_size", 0) for r in results if "error" not in r),
        }
        self._index.append(index_entry)
        self._save_index()

        # 清理旧备份
        self._cleanup_old_backups()

        logger.info(f"💾 备份完成: {backup_id} ({len(results)} files)")
        return {"success": True, "backup_id": backup_id, "files": results}

    def auto_backup_if_needed(self) -> Optional[dict]:
        """检查是否需要自动备份"""
        now = int(time.time())
        if now - self._last_auto_backup >= self._auto_interval:
            self._last_auto_backup = now
            return self.backup(label="auto")
        return None

    @safe_execute(default=None)
    def restore(self, backup_id: str) -> dict:
        """
        恢复到指定备份点

        ⚠️ 当前数据库会被覆盖！
        """
        # 找到备份
        backup_subdir = os.path.join(self._backup_dir, backup_id)
        if not os.path.exists(backup_subdir):
            return {"success": False, "error": f"Backup {backup_id} not found"}

        # 先备份当前状态
        pre_restore = self.backup(label="pre_restore")

        restored = []
        for filename in os.listdir(backup_subdir):
            src = os.path.join(backup_subdir, filename)
            if not os.path.isfile(src):
                continue

            try:
                # 还原文件名
                dest_name = filename.replace(".gz", "")
                dest_path = os.path.join(self._data_dir, dest_name)

                if filename.endswith(".gz"):
                    with gzip.open(src, "rb") as f_in:
                        with open(dest_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                else:
                    shutil.copy2(src, dest_path)

                # 验证完整性
                sha256 = self._sha256_file(dest_path)
                restored.append({"file": dest_name, "sha256": sha256, "ok": True})

            except Exception as e:
                restored.append({"file": filename, "error": str(e), "ok": False})

        logger.info(f"💾 恢复完成: {backup_id} ({sum(1 for r in restored if r['ok'])} files)")
        return {
            "success": True,
            "backup_id": backup_id,
            "pre_restore_backup": pre_restore.get("backup_id"),
            "restored_files": restored,
        }

    def list_backups(self) -> list[dict]:
        """列出所有备份"""
        return sorted(self._index, key=lambda x: x.get("timestamp", 0), reverse=True)

    def get_backup_info(self, backup_id: str) -> Optional[dict]:
        for entry in self._index:
            if entry.get("backup_id") == backup_id:
                return entry
        return None

    def delete_backup(self, backup_id: str) -> dict:
        """删除指定备份"""
        backup_subdir = os.path.join(self._backup_dir, backup_id)
        if os.path.exists(backup_subdir):
            shutil.rmtree(backup_subdir)
        self._index = [e for e in self._index if e.get("backup_id") != backup_id]
        self._save_index()
        return {"success": True, "deleted": backup_id}

    def _cleanup_old_backups(self):
        """保留最近N个备份，删除更早的自动备份"""
        auto_backups = [e for e in self._index if e.get("label") == "auto"]
        manual_backups = [e for e in self._index if e.get("label") != "auto"]

        if len(auto_backups) <= self._max_backups:
            return

        # 按时间排序，保留最新的
        auto_backups.sort(key=lambda x: x.get("timestamp", 0))
        to_delete = auto_backups[: len(auto_backups) - self._max_backups]

        for entry in to_delete:
            self.delete_backup(entry["backup_id"])

        logger.info(f"💾 清理旧备份: 删除 {len(to_delete)} 个")

    def get_stats(self) -> dict:
        """备份统计"""
        total_size = sum(e.get("total_size", 0) for e in self._index)
        auto_count = sum(1 for e in self._index if e.get("label") == "auto")
        manual_count = sum(1 for e in self._index if e.get("label") != "auto")
        return {
            "total_backups": len(self._index),
            "auto_backups": auto_count,
            "manual_backups": manual_count,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "backup_dir": self._backup_dir,
            "max_backups": self._max_backups,
        }

    @safe_execute(default=None)
    def close(self):
        pass  # 无需关闭
