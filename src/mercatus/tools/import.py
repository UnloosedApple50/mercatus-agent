"""Import data from JSON/CSV."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Optional

from mercatus.db.database import Database, db
from mercatus.utils.logger import get_logger

logger = get_logger("tools.import")


class DataImporter:
    """Import agent data from various formats."""

    def __init__(self, database: Optional[Database] = None) -> None:
        self._db = database or db

    async def import_semantic_memory(
        self,
        data: str,
        format: str = "json",
    ) -> int:
        """Import semantic memory entries.

        Args:
            data: JSON string or CSV string.
            format: "json" or "csv".

        Returns:
            Number of entries imported.
        """
        if format == "csv":
            reader = csv.DictReader(io.StringIO(data))
            entries = list(reader)
        else:
            entries = json.loads(data)

        count = 0
        for entry in entries:
            try:
                await self._db.execute(
                    """
                    INSERT OR REPLACE INTO semantic_memory 
                    (module, category, key, value, confidence, source, tags, use_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.get("module", "general"),
                        entry.get("category", "imported"),
                        entry.get("key", "unknown"),
                        entry.get("value", ""),
                        float(entry.get("confidence", 0.5)),
                        entry.get("source", "import"),
                        entry.get("tags", "[]"),
                        int(entry.get("use_count", 0)),
                    ),
                )
                await self._db.commit()
                count += 1
            except Exception as e:
                logger.error(f"Import error: {e}")

        logger.info(f"Imported {count} semantic memory entries")
        return count

    async def import_episodic_memory(
        self,
        data: str,
        format: str = "json",
    ) -> int:
        """Import episodic memory entries."""
        if format == "csv":
            reader = csv.DictReader(io.StringIO(data))
            entries = list(reader)
        else:
            entries = json.loads(data)

        count = 0
        for entry in entries:
            try:
                await self._db.execute(
                    """
                    INSERT INTO episodic_memory 
                    (session_id, module, query, response, confidence, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.get("session_id", "imported"),
                        entry.get("module", "general"),
                        entry.get("query", ""),
                        entry.get("response", ""),
                        float(entry.get("confidence", 0.5)),
                        entry.get("metadata", "{}"),
                    ),
                )
                await self._db.commit()
                count += 1
            except Exception as e:
                logger.error(f"Import error: {e}")

        logger.info(f"Imported {count} episodic memory entries")
        return count


data_importer = DataImporter()
