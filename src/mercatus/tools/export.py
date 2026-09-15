"""Export data (memory, decisions, conversations) to JSON/CSV."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any, Literal

from mercatus.db.database import Database, db
from mercatus.utils.logger import get_logger

logger = get_logger("tools.export")


class DataExporter:
    """Export agent data to various formats."""

    def __init__(self, database: Database | None = None) -> None:
        self._db = database or db

    async def export_episodic_memory(
        self,
        format: Literal["json", "csv"] = "json",
        session_id: str | None = None,
        module: str | None = None,
    ) -> str:
        """Export episodic memory data."""
        query = "SELECT * FROM episodic_memory WHERE 1=1"
        params: list[Any] = []

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if module:
            query += " AND module = ?"
            params.append(module)

        query += " ORDER BY created_at DESC"
        rows = await self._db.fetchall(query, tuple(params) if params else None)

        columns = [
            "id", "session_id", "module", "query", "response",
            "confidence", "outcome", "outcome_score", "metadata",
            "created_at", "updated_at",
        ]

        data = []
        for row in rows:
            data.append({col: row[col] for col in columns})

        if format == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data)
            return output.getvalue()
        return json.dumps(data, indent=2, default=str)

    async def export_semantic_memory(
        self,
        format: Literal["json", "csv"] = "json",
        module: str | None = None,
    ) -> str:
        """Export semantic memory data."""
        query = "SELECT * FROM semantic_memory WHERE 1=1"
        params: list[Any] = []

        if module:
            query += " AND module = ?"
            params.append(module)

        query += " ORDER BY confidence DESC"
        rows = await self._db.fetchall(query, tuple(params) if params else None)

        columns = [
            "id", "module", "category", "key", "value",
            "confidence", "source", "tags", "use_count",
            "created_at", "updated_at",
        ]

        data = []
        for row in rows:
            data.append({col: row[col] for col in columns})

        if format == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data)
            return output.getvalue()
        return json.dumps(data, indent=2, default=str)

    async def export_decisions(
        self,
        format: Literal["json", "csv"] = "json",
        module: str | None = None,
    ) -> str:
        """Export decision history."""
        query = "SELECT * FROM decisions WHERE 1=1"
        params: list[Any] = []

        if module:
            query += " AND module = ?"
            params.append(module)

        query += " ORDER BY created_at DESC"
        rows = await self._db.fetchall(query, tuple(params) if params else None)

        columns = [
            "id", "session_id", "module", "context", "options",
            "selected_option", "confidence", "reasoning", "outcome",
            "created_at",
        ]

        data = []
        for row in rows:
            data.append({col: row[col] for col in columns})

        if format == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data)
            return output.getvalue()
        return json.dumps(data, indent=2, default=str)

    async def export_conversations(
        self,
        format: Literal["json", "csv"] = "json",
    ) -> str:
        """Export full conversation history grouped by session."""
        sessions = await self._db.fetchall(
            "SELECT * FROM sessions ORDER BY last_active DESC"
        )

        conversations = []
        for sess in sessions:
            sid = sess["id"] if isinstance(sess["id"], str) else sess[0]
            messages = await self._db.fetchall(
                "SELECT * FROM episodic_memory WHERE session_id = ? ORDER BY created_at",
                (sid,)
            )
            conversations.append({
                "session_id": sid,
                "module": sess["module"] if isinstance(sess["module"], str) else sess[1],
                "message_count": sess["message_count"] if isinstance(sess["message_count"], int) else sess[2],
                "started_at": sess["started_at"] if isinstance(sess["started_at"], str) else sess[3],
                "last_active": sess["last_active"] if isinstance(sess["last_active"], str) else sess[4],
                "messages": [
                    {
                        "query": m["query"] if isinstance(m["query"], str) else m[3],
                        "response": m["response"] if isinstance(m["response"], str) else m[4],
                        "confidence": m["confidence"] if isinstance(m["confidence"], (int, float)) else m[5],
                        "created_at": m["created_at"] if isinstance(m["created_at"], str) else m[7],
                    }
                    for m in messages
                ],
            })

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["session_id", "module", "query", "response", "confidence", "timestamp"])
            for conv in conversations:
                for msg in conv["messages"]:
                    writer.writerow([
                        conv["session_id"], conv["module"],
                        msg["query"], msg["response"],
                        msg["confidence"], msg["created_at"],
                    ])
            return output.getvalue()
        return json.dumps(conversations, indent=2, default=str)

    async def export_all(self, format: Literal["json", "csv"] = "json") -> dict[str, str]:
        """Export all data types."""
        return {
            "episodic_memory": await self.export_episodic_memory(format),
            "semantic_memory": await self.export_semantic_memory(format),
            "decisions": await self.export_decisions(format),
            "conversations": await self.export_conversations(format),
        }


data_exporter = DataExporter()
