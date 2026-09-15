"""Obsidian vault integration — generate markdown vaults from Mercatus data."""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mercatus.db.database import Database
from mercatus.utils.logger import get_logger

logger = get_logger("obsidian")


class ObsidianVaultGenerator:
    """Generates a complete Obsidian vault from Mercatus agent data."""

    def __init__(self, database: Database, output_dir: Optional[str] = None) -> None:
        self._db = database
        self._output_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="mercatus-vault-"))

    async def generate_vault(self) -> Path:
        """
        Generate the complete Obsidian vault.

        Returns:
            Path to the generated vault directory.
        """
        vault_dir = self._output_dir / "mercatus-vault"
        vault_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (vault_dir / "Memory").mkdir(exist_ok=True)
        (vault_dir / "Decisions").mkdir(exist_ok=True)
        (vault_dir / "Knowledge").mkdir(exist_ok=True)
        (vault_dir / "Conversations").mkdir(exist_ok=True)

        # Create .obsidian config
        await self._create_obsidian_config(vault_dir)

        # Generate content files
        await self._generate_memory_notes(vault_dir / "Memory")
        await self._generate_decision_notes(vault_dir / "Decisions")
        await self._generate_knowledge_notes(vault_dir / "Knowledge")
        await self._generate_conversation_notes(vault_dir / "Conversations")

        # Generate index/MOC
        await self._generate_index(vault_dir)

        logger.info(f"Obsidian vault generated at {vault_dir}")
        return vault_dir

    async def export_as_zip(self) -> Path:
        """
        Generate vault and export as ZIP file.

        Returns:
            Path to the ZIP file.
        """
        vault_dir = await self.generate_vault()
        zip_path = self._output_dir / "mercatus-vault.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(vault_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(vault_dir.parent)
                    zf.write(file_path, arcname)

        logger.info(f"Vault exported as ZIP: {zip_path}")
        return zip_path

    async def sync_vault(self) -> dict[str, Any]:
        """
        Sync vault — regenerate and return stats.

        Returns:
            Sync statistics.
        """
        vault_dir = await self.generate_vault()

        stats = {
            "vault_path": str(vault_dir),
            "memory_notes": len(list((vault_dir / "Memory").glob("*.md"))),
            "decision_notes": len(list((vault_dir / "Decisions").glob("*.md"))),
            "knowledge_notes": len(list((vault_dir / "Knowledge").glob("*.md"))),
            "conversation_notes": len(list((vault_dir / "Conversations").glob("*.md"))),
            "synced_at": datetime.utcnow().isoformat(),
        }

        stats["total_notes"] = (
            stats["memory_notes"]
            + stats["decision_notes"]
            + stats["knowledge_notes"]
            + stats["conversation_notes"]
        )

        return stats

    async def _create_obsidian_config(self, vault_dir: Path) -> None:
        """Create .obsidian configuration directory."""
        obsidian_dir = vault_dir / ".obsidian"
        obsidian_dir.mkdir(exist_ok=True)

        # app.json
        app_config = {
            "alwaysUpdateLinks": True,
            "useMarkdownLinks": False,
            "newLinkFormat": "shortest",
            "attachmentFolderPath": "attachments",
        }
        (obsidian_dir / "app.json").write_text(json.dumps(app_config, indent=2))

        # appearance.json
        appearance = {
            "theme": "moonstone",
            "baseFontSize": 16,
            "translucency": False,
        }
        (obsidian_dir / "appearance.json").write_text(json.dumps(appearance, indent=2))

        # core-plugins.json
        plugins = [
            "file-explorer",
            "global-search",
            "switcher",
            "graph-view",
            "backlink",
            "outgoing-link",
            "tag-pane",
            "page-preview",
            "templates",
            "note-composer",
            "command-palette",
            "editor-status",
            "markdown-importer",
            "word-count",
            "open-with-default-app",
            "file-recovery",
        ]
        (obsidian_dir / "core-plugins.json").write_text(json.dumps(plugins, indent=2))

        # graph.json (graph view config)
        graph_config = {
            "collapse-filter": False,
            "search": "",
            "showTags": True,
            "showAttachments": False,
            "hideUnresolved": False,
            "showOrphans": True,
            "collapse-color-groups": False,
            "colorGroups": [],
            "collapse-display": False,
            "showArrow": True,
            "textFadeMultiplier": 0,
            "nodeSizeMultiplier": 1,
            "lineSizeMultiplier": 1,
            "collapse-forces": False,
            "centerStrength": 0.5,
            "repelStrength": 10,
            "linkStrength": 1,
            "linkDistance": 250,
            "scale": 1,
            "close": False,
        }
        (obsidian_dir / "graph.json").write_text(json.dumps(graph_config, indent=2))

        # Empty plugins directory
        (obsidian_dir / "plugins").mkdir(exist_ok=True)

    async def _generate_memory_notes(self, memory_dir: Path) -> None:
        """Generate markdown notes for episodic memories."""
        rows = await self._db.fetchall(
            "SELECT * FROM episodic_memory ORDER BY created_at DESC LIMIT 500"
        )

        for row in rows:
            memory_id = row[0] if isinstance(row[0], int) else row["id"]
            session_id = row[1] if isinstance(row[1], str) else row["session_id"]
            module = row[2] if isinstance(row[2], str) else row["module"]
            query = row[3] if isinstance(row[3], str) else row["query"]
            response = row[4] if isinstance(row[4], str) else row["response"]
            confidence = row[5] if isinstance(row[5], (int, float)) else row["confidence"]
            outcome = row[6] if isinstance(row[6], str) else row["outcome"]
            outcome_score = row[7] if isinstance(row[7], (int, float)) else row["outcome_score"]
            metadata_raw = row[9] if isinstance(row[9], str) else row["created_at"]
            created_at = row[8] if isinstance(row[8], str) else row["created_at"]

            # Build frontmatter
            frontmatter = {
                "type": "memory",
                "module": module,
                "session": session_id,
                "confidence": float(confidence) if confidence else 0.5,
                "created": created_at,
                "tags": ["memory", module],
                "outcome": outcome or "",
            }

            if outcome_score is not None:
                frontmatter["outcome_score"] = float(outcome_score)

            # Build content
            content = self._build_markdown(frontmatter, [
                f"## Query\n\n{query}",
                f"## Response\n\n{response}",
                f"## Metadata\n",
                f"- Session: [[{session_id[:8]}]]",
                f"- Confidence: {float(confidence):.0%}",
            ])

            # Write file
            safe_name = self._sanitize_filename(f"memory_{memory_id}_{query[:40]}")
            (memory_dir / f"{safe_name}.md").write_text(content, encoding="utf-8")

    async def _generate_decision_notes(self, decisions_dir: Path) -> None:
        """Generate markdown notes for decisions."""
        rows = await self._db.fetchall(
            "SELECT * FROM decisions ORDER BY created_at DESC LIMIT 200"
        )

        for row in rows:
            decision_id = row[0] if isinstance(row[0], int) else row["id"]
            session_id = row[1] if isinstance(row[1], str) else row["session_id"]
            module = row[2] if isinstance(row[2], str) else row["module"]
            context = row[3] if isinstance(row[3], str) else row["context"]
            options_raw = row[4] if isinstance(row[4], str) else row["options"]
            selected = row[5] if isinstance(row[5], str) else row["selected_option"]
            confidence_raw = row[5] if isinstance(row[5], (int, float)) else row["confidence"]
            reasoning = row[6] if isinstance(row[6], str) else row["reasoning"]
            outcome = row[7] if isinstance(row[7], str) else row["outcome"]
            created_at = row[8] if isinstance(row[8], str) else row["created_at"]

            try:
                options = json.loads(options_raw) if options_raw else []
            except (json.JSONDecodeError, TypeError):
                options = []

            confidence = float(confidence_raw) if confidence_raw else 0.5

            frontmatter = {
                "type": "decision",
                "module": module,
                "session": session_id,
                "confidence": confidence,
                "selected": selected or "",
                "created": created_at,
                "tags": ["decision", module],
                "outcome": outcome or "",
            }

            option_lines = "\n".join(f"- {opt}" for opt in options)
            content = self._build_markdown(frontmatter, [
                f"## Context\n\n{context}",
                f"## Options\n\n{option_lines}",
                f"## Selection\n\n**{selected}**" if selected else "## Selection\n\n_Pending_",
                f"## Reasoning\n\n{reasoning or 'No reasoning recorded.'}",
                f"## Related\n",
                f"- Session: [[{session_id[:8]}]]",
            ])

            safe_name = self._sanitize_filename(f"decision_{decision_id}_{context[:40]}")
            (decisions_dir / f"{safe_name}.md").write_text(content, encoding="utf-8")

    async def _generate_knowledge_notes(self, knowledge_dir: Path) -> None:
        """Generate markdown notes for semantic knowledge."""
        rows = await self._db.fetchall(
            "SELECT * FROM semantic_memory ORDER BY category, key"
        )

        for row in rows:
            knowledge_id = row[0] if isinstance(row[0], int) else row["id"]
            module = row[1] if isinstance(row[1], str) else row["module"]
            category = row[2] if isinstance(row[2], str) else row["category"]
            key = row[3] if isinstance(row[3], str) else row["key"]
            value = row[4] if isinstance(row[4], str) else row["value"]
            confidence = row[5] if isinstance(row[5], (int, float)) else row["confidence"]
            source = row[6] if isinstance(row[6], str) else row["source"]
            tags_raw = row[7] if isinstance(row[7], str) else row["tags"]
            use_count = row[8] if isinstance(row[8], int) else row["use_count"]

            try:
                tags = json.loads(tags_raw) if tags_raw else []
            except (json.JSONDecodeError, TypeError):
                tags = []

            all_tags = ["knowledge", module, category] + tags

            frontmatter = {
                "type": "knowledge",
                "module": module,
                "category": category,
                "confidence": float(confidence) if confidence else 0.5,
                "source": source or "system",
                "use_count": use_count or 0,
                "tags": all_tags,
            }

            content = self._build_markdown(frontmatter, [
                f"## Value\n\n{value}",
                f"## Metadata\n",
                f"- Module: `{module}`",
                f"- Category: `{category}`",
                f"- Confidence: {float(confidence):.0%}",
                f"- Source: {source}",
                f"- Use count: {use_count}",
            ])

            safe_name = self._sanitize_filename(f"{category}_{key}")
            (knowledge_dir / f"{safe_name}.md").write_text(content, encoding="utf-8")

    async def _generate_conversation_notes(self, conversations_dir: Path) -> None:
        """Generate markdown notes for conversations (grouped by session)."""
        # Get distinct sessions
        rows = await self._db.fetchall(
            """
            SELECT session_id, module, COUNT(*) as msg_count,
                   MIN(created_at) as start_time,
                   MAX(created_at) as end_time
            FROM episodic_memory
            WHERE session_id IS NOT NULL AND session_id != ''
            GROUP BY session_id
            ORDER BY end_time DESC
            LIMIT 100
            """
        )

        for row in rows:
            session_id = row[0] if isinstance(row[0], str) else row["session_id"]
            module = row[1] if isinstance(row[1], str) else row["module"]
            msg_count = row[2] if isinstance(row[2], int) else row["msg_count"]
            start_time = row[3] if isinstance(row[3], str) else row["start_time"]
            end_time = row[4] if isinstance(row[4], str) else row["end_time"]

            # Get messages in this session
            messages = await self._db.fetchall(
                "SELECT query, response, confidence, created_at FROM episodic_memory WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            )

            frontmatter = {
                "type": "conversation",
                "module": module,
                "session": session_id,
                "message_count": msg_count,
                "started": start_time,
                "ended": end_time,
                "tags": ["conversation", module],
            }

            message_blocks = []
            for i, msg in enumerate(messages, 1):
                query = msg[0] if isinstance(msg[0], str) else msg["query"]
                response = msg[1] if isinstance(msg[1], str) else msg["response"]
                conf = msg[2] if isinstance(msg[2], (int, float)) else msg["confidence"]
                message_blocks.append(
                    f"### Message {i}\n\n"
                    f"**Q:** {query}\n\n"
                    f"**A:** {response}\n\n"
                    f"_Confidence: {float(conf):.0%}_\n"
                )

            content = self._build_markdown(frontmatter, [
                f"## Conversation ({msg_count} messages)\n",
                "\n---\n".join(message_blocks),
            ])

            safe_name = self._sanitize_filename(f"conversation_{session_id[:12]}")
            (conversations_dir / f"{safe_name}.md").write_text(content, encoding="utf-8")

    async def _generate_index(self, vault_dir: Path) -> None:
        """Generate the index/MOC (Map of Content) note."""
        # Count items
        memory_count = await self._db.fetchval("SELECT COUNT(*) FROM episodic_memory") or 0
        decision_count = await self._db.fetchval("SELECT COUNT(*) FROM decisions") or 0
        knowledge_count = await self._db.fetchval("SELECT COUNT(*) FROM semantic_memory") or 0
        session_count = await self._db.fetchval("SELECT COUNT(*) FROM sessions") or 0

        frontmatter = {
            "type": "index",
            "tags": ["index", "moc"],
        }

        content = self._build_markdown(frontmatter, [
            "# Mercatus Agent — Knowledge Map\n",
            "## Overview\n",
            f"- **Episodic Memories**: {memory_count}",
            f"- **Decisions**: {decision_count}",
            f"- **Knowledge Items**: {knowledge_count}",
            f"- **Sessions**: {session_count}\n",
            "## Vault Structure\n",
            "- [[Memory/]] — Episodic memories from conversations",
            "- [[Decisions/]] — Decision history with context",
            "- [[Knowledge/]] — Semantic knowledge base",
            "- [[Conversations/]] — Full conversation logs\n",
            "## Modules\n",
            "- [[sales]] — Sales strategies and tactics",
            "- [[trading]] — Trading analysis and risk management",
            "- [[general]] — General advisory\n",
            "## Tags\n",
            "- `#memory` — Episodic memory entries",
            "- `#decision` — Decision records",
            "- `#knowledge` — Knowledge facts",
            "- `#conversation` — Conversation logs",
        ])

        (vault_dir / "Index.md").write_text(content, encoding="utf-8")

    def _build_markdown(self, frontmatter: dict[str, Any], sections: list[str]) -> str:
        """Build a markdown file with YAML frontmatter."""
        lines = ["---"]

        for key, value in frontmatter.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            elif isinstance(value, float):
                lines.append(f"{key}: {value:.2f}")
            else:
                lines.append(f"{key}: {value}")

        lines.append("---")
        lines.append("")
        lines.extend(sections)
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a string for use as a filename."""
        # Replace problematic characters
        result = ""
        for char in name:
            if char.isalnum() or char in "._- ":
                result += char
            else:
                result += "_"

        # Limit length
        result = result.strip()[:80]
        if not result:
            result = "untitled"

        return result
