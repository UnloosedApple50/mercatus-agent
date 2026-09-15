"""Health check and self-diagnostic system."""

from __future__ import annotations

import os
import platform
import time
from dataclasses import dataclass
from typing import Any

from mercatus.db.database import Database, db
from mercatus.utils.logger import get_logger

logger = get_logger("tools.health")


@dataclass
class HealthStatus:
    """Overall system health status."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: float
    checks: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "timestamp": self.timestamp,
            "checks": self.checks,
        }


class HealthChecker:
    """Performs comprehensive health checks on all system components."""

    def __init__(self, database: Database | None = None) -> None:
        self._db = database or db

    async def run_full_check(self) -> HealthStatus:
        """Run all health checks."""
        checks: dict[str, dict[str, Any]] = {}

        # Database check
        checks["database"] = await self._check_database()

        # Disk space check
        checks["disk"] = self._check_disk_space()

        # Memory check
        checks["memory"] = self._check_memory()

        # LLM connectivity (basic)
        checks["llm"] = await self._check_llm()

        # Overall status
        statuses = [c.get("status", "unknown") for c in checks.values()]
        if all(s == "ok" for s in statuses):
            overall = "healthy"
        elif any(s == "critical" for s in statuses):
            overall = "unhealthy"
        else:
            overall = "degraded"

        return HealthStatus(
            status=overall,
            timestamp=time.time(),
            checks=checks,
        )

    async def _check_database(self) -> dict[str, Any]:
        """Check database connectivity and integrity."""
        try:
            if not self._db.is_connected:
                return {"status": "critical", "message": "Database not connected"}

            # Test query
            result = await self._db.fetchval("SELECT COUNT(*) FROM episodic_memory")
            return {
                "status": "ok",
                "message": "Database connected",
                "episodic_count": result,
            }
        except Exception as e:
            return {"status": "critical", "message": f"Database error: {e}"}

    def _check_disk_space(self) -> dict[str, Any]:
        """Check available disk space."""
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            percent_used = (used / total) * 100

            if percent_used > 95:
                status = "critical"
            elif percent_used > 85:
                status = "warning"
            else:
                status = "ok"

            return {
                "status": status,
                "percent_used": round(percent_used, 1),
                "free_gb": round(free / (1024**3), 2),
                "total_gb": round(total / (1024**3), 2),
            }
        except Exception:
            return {"status": "unknown", "message": "Could not check disk"}

    def _check_memory(self) -> dict[str, Any]:
        """Check system memory usage."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "status": "ok" if mem.percent < 90 else "warning",
                "percent_used": mem.percent,
                "available_gb": round(mem.available / (1024**3), 2),
            }
        except ImportError:
            return {"status": "ok", "message": "psutil not available"}

    async def _check_llm(self) -> dict[str, Any]:
        """Check LLM service connectivity."""
        from mercatus.models.llm import llm_client
        try:
            available = llm_client.is_available
            return {
                "status": "ok" if available else "warning",
                "connected": available,
                "model": llm_client._settings.llm_model if available else None,
            }
        except Exception:
            return {"status": "warning", "message": "LLM check failed"}

    async def get_diagnostics(self) -> dict[str, Any]:
        """Get detailed diagnostic information."""
        return {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "hostname": platform.node(),
            },
            "environment": {
                "pid": os.getpid(),
                "cwd": os.getcwd(),
            },
            "health": (await self.run_full_check()).to_dict(),
        }


health_checker = HealthChecker()
