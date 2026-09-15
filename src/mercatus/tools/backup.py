"""Automated backup scheduling and management."""

from __future__ import annotations

import json
import os
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from mercatus.db.database import Database, db
from mercatus.utils.logger import get_logger

logger = get_logger("tools.backup")


@dataclass
class BackupInfo:
    """Metadata about a backup."""
    filename: str
    created_at: str
    size_bytes: int
    description: str = ""
    tags: List[str] = field(default_factory=list)


class BackupManager:
    """Manages database and data backups."""

    def __init__(
        self,
        backup_dir: str = "./backups",
        database: Optional[Database] = None,
    ) -> None:
        self._backup_dir = Path(backup_dir)
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._db = database or db

    def create_backup(
        self,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> BackupInfo:
        """Create a full backup of the database and exports."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"mercatus_backup_{timestamp}.zip"
        filepath = self._backup_dir / filename

        with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add database file
            db_path = self._db._db_path
            if db_path.exists():
                zf.write(db_path, "database/mercatus.db")

            # Add schema SQL
            schema_sql = self._get_schema_sql()
            zf.writestr("database/schema.sql", schema_sql)

            # Add metadata
            meta = {
                "created_at": datetime.utcnow().isoformat(),
                "description": description,
                "tags": tags or [],
                "version": "2.0.0",
            }
            zf.writestr("metadata.json", json.dumps(meta, indent=2))

        size = filepath.stat().st_size
        logger.info(f"Backup created: {filename} ({size} bytes)")

        return BackupInfo(
            filename=filename,
            created_at=meta["created_at"],
            size_bytes=size,
            description=description,
            tags=tags or [],
        )

    def _get_schema_sql(self) -> str:
        """Get database schema as SQL."""
        return """-- Mercatus Agent Database Schema
-- Generated backup schema

CREATE TABLE IF NOT EXISTS episodic_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    module TEXT NOT NULL DEFAULT 'general',
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    outcome TEXT,
    outcome_score REAL,
    metadata TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL DEFAULT 'general',
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    source TEXT DEFAULT 'system',
    tags TEXT DEFAULT '[]',
    use_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(module, category, key)
);
"""

    def restore_backup(self, filename: str) -> bool:
        """Restore from a backup ZIP file."""
        filepath = self._backup_dir / filename
        if not filepath.exists():
            logger.error(f"Backup not found: {filename}")
            return False

        try:
            with zipfile.ZipFile(filepath, "r") as zf:
                # Extract database
                if "database/mercatus.db" in zf.namelist():
                    zf.extract("database", self._backup_dir / "restore_temp")
                    temp_db = self._backup_dir / "restore_temp" / "mercatus.db"
                    shutil.copy2(str(temp_db), str(self._db._db_path))
                    shutil.rmtree(self._backup_dir / "restore_temp")

            logger.info(f"Backup restored: {filename}")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    def list_backups(self) -> List[BackupInfo]:
        """List all available backups."""
        backups = []
        for f in sorted(self._backup_dir.glob("mercatus_backup_*.zip")):
            stat = f.stat()
            backups.append(BackupInfo(
                filename=f.name,
                created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                size_bytes=stat.st_size,
            ))
        return backups

    def delete_backup(self, filename: str) -> bool:
        """Delete a backup file."""
        filepath = self._backup_dir / filename
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def get_backup_path(self, filename: str) -> Path:
        """Get the full path to a backup file."""
        return self._backup_dir / filename


backup_manager = BackupManager()
