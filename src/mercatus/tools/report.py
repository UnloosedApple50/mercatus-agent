"""Generate usage reports."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from mercatus.db.database import Database, db
from mercatus.utils.logger import get_logger

logger = get_logger("tools.report")


class ReportGenerator:
    """Generate comprehensive usage reports."""

    def __init__(self, database: Optional[Database] = None) -> None:
        self._db = database or db

    async def generate_usage_report(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Generate a usage report for the specified period."""
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Conversation stats
        conv_row = await self._db.fetchone(
            """
            SELECT COUNT(DISTINCT session_id) as sessions,
                   COUNT(*) as messages
            FROM episodic_memory
            WHERE created_at >= ?
            """,
            (since,),
        )
        sessions = conv_row[0] if conv_row else 0
        messages = conv_row[1] if conv_row else 0

        # Decision stats
        dec_row = await self._db.fetchone(
            """
            SELECT COUNT(*) as decisions,
                   AVG(confidence) as avg_confidence
            FROM decisions
            WHERE created_at >= ?
            """,
            (since,),
        )
        decisions = dec_row[0] if dec_row else 0
        avg_confidence = round(dec_row[1], 2) if dec_row and dec_row[1] else 0

        # Knowledge stats
        kb_row = await self._db.fetchone(
            "SELECT COUNT(*) as facts FROM semantic_memory",
        )
        knowledge_facts = kb_row[0] if kb_row else 0

        # Module breakdown
        module_rows = await self._db.fetchall(
            """
            SELECT module, COUNT(*) as count
            FROM episodic_memory
            WHERE created_at >= ?
            GROUP BY module
            """,
            (since,),
        )
        module_breakdown = {
            row[0] if isinstance(row[0], str) else row["module"]:
            row[1] if isinstance(row[1], int) else row["count"]
            for row in module_rows
        }

        # Daily activity
        daily_rows = await self._db.fetchall(
            """
            SELECT DATE(created_at) as day, COUNT(*) as count
            FROM episodic_memory
            WHERE created_at >= ?
            GROUP BY DATE(created_at)
            ORDER BY day
            """,
            (since,),
        )
        daily_activity = [
            {
                "date": row[0] if isinstance(row[0], str) else row["day"],
                "count": row[1] if isinstance(row[1], int) else row["count"],
            }
            for row in daily_rows
        ]

        return {
            "period_days": days,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_sessions": sessions,
                "total_messages": messages,
                "total_decisions": decisions,
                "knowledge_facts": knowledge_facts,
                "avg_decision_confidence": avg_confidence,
            },
            "module_breakdown": module_breakdown,
            "daily_activity": daily_activity,
        }

    async def generate_performance_report(self) -> Dict[str, Any]:
        """Generate LLM performance report."""
        metrics_row = await self._db.fetchone(
            """
            SELECT 
                COUNT(*) as total_requests,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(AVG(tokens_per_second), 0) as avg_tps,
                COALESCE(AVG(latency_ms), 0) as avg_latency,
                COALESCE(MAX(tokens_per_second), 0) as peak_tps
            FROM metrics_throughput
            """,
        )

        if metrics_row:
            return {
                "total_requests": metrics_row[0] or 0,
                "total_tokens": metrics_row[1] or 0,
                "avg_tps": round(metrics_row[2] or 0, 2),
                "avg_latency_ms": round(metrics_row[3] or 0, 2),
                "peak_tps": round(metrics_row[4] or 0, 2),
            }
        return {
            "total_requests": 0,
            "total_tokens": 0,
            "avg_tps": 0,
            "avg_latency_ms": 0,
            "peak_tps": 0,
        }

    async def generate_security_report(self) -> Dict[str, Any]:
        """Generate security audit report."""
        # Audit log entries
        audit_rows = await self._db.fetchall(
            "SELECT action, COUNT(*) as count FROM audit_log GROUP BY action ORDER BY count DESC"
        )
        audit_summary = {
            row[0] if isinstance(row[0], str) else row["action"]:
            row[1] if isinstance(row[1], int) else row["count"]
            for row in audit_rows
        }

        # API keys
        key_row = await self._db.fetchone(
            "SELECT COUNT(*) as total, SUM(active) as active FROM api_keys"
        )
        total_keys = key_row[0] if key_row else 0
        active_keys = key_row[1] if key_row else 0

        # Recent audit entries
        recent_audit = await self._db.fetchall(
            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 20"
        )

        return {
            "audit_summary": audit_summary,
            "api_keys": {
                "total": total_keys,
                "active": active_keys,
            },
            "recent_audit_entries": len(recent_audit),
        }


report_generator = ReportGenerator()
