"""Main entry point for Mercatus Agent."""

from __future__ import annotations

import sys
import asyncio
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main() -> None:
    """Run the Mercatus Agent server."""
    import uvicorn
    from mercatus.models.config import get_settings

    settings = get_settings()

    uvicorn.run(
        "mercatus.server.api:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
        access_log=True,
    )


def init_db() -> None:
    """Initialize the database."""
    from mercatus.db.database import db
    from mercatus.db.migrations import init_schema, seed_knowledge

    async def _init():
        await db.initialize()
        await init_schema(db)
        await seed_knowledge(db)
        await db.close()
        print("Database initialized successfully.")

    asyncio.run(_init())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "db" and sys.argv[2] == "init":
        init_db()
    else:
        main()
