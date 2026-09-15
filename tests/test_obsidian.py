"""Tests for Obsidian vault integration."""

from __future__ import annotations

import pytest
import pytest_asyncio
import zipfile
import tempfile
from pathlib import Path
from typing import AsyncGenerator

from mercatus.integrations.obsidian import ObsidianVaultGenerator
from mercatus.db.database import Database
from mercatus.db.migrations import init_schema, seed_knowledge


@pytest_asyncio.fixture
async def obsidian_db() -> AsyncGenerator[Database, None]:
    """Create a test database with seeded knowledge."""
    db = Database(":memory:")
    await db.initialize()
    await init_schema(db)
    await seed_knowledge(db)
    yield db
    await db.close()


@pytest_asyncio.fixture
async def obsidian_generator(obsidian_db: Database) -> ObsidianVaultGenerator:
    """Create an Obsidian vault generator."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ObsidianVaultGenerator(obsidian_db, output_dir=tmpdir)


class TestObsidianVaultGenerator:
    """Tests for ObsidianVaultGenerator."""

    @pytest.mark.asyncio
    async def test_init(self, obsidian_db: Database):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ObsidianVaultGenerator(obsidian_db, output_dir=tmpdir)
            assert gen._db == obsidian_db
            assert gen._output_dir == Path(tmpdir)

    @pytest.mark.asyncio
    async def test_generate_vault(self, obsidian_generator: ObsidianVaultGenerator):
        vault_dir = await obsidian_generator.generate_vault()
        assert vault_dir.exists()
        assert vault_dir.name == "mercatus-vault"

    @pytest.mark.asyncio
    async def test_vault_has_obsidian_config(self, obsidian_generator: ObsidianVaultGenerator):
        vault_dir = await obsidian_generator.generate_vault()
        obsidian_dir = vault_dir / ".obsidian"
        assert obsidian_dir.exists()
        assert (obsidian_dir / "app.json").exists()
        assert (obsidian_dir / "appearance.json").exists()
        assert (obsidian_dir / "core-plugins.json").exists()

    @pytest.mark.asyncio
    async def test_vault_has_directories(self, obsidian_generator: ObsidianVaultGenerator):
        vault_dir = await obsidian_generator.generate_vault()
        assert (vault_dir / "Memory").exists()
        assert (vault_dir / "Decisions").exists()
        assert (vault_dir / "Knowledge").exists()
        assert (vault_dir / "Conversations").exists()

    @pytest.mark.asyncio
    async def test_vault_has_index(self, obsidian_generator: ObsidianVaultGenerator):
        vault_dir = await obsidian_generator.generate_vault()
        assert (vault_dir / "Index.md").exists()

    @pytest.mark.asyncio
    async def test_vault_has_knowledge_notes(self, obsidian_generator: ObsidianVaultGenerator):
        vault_dir = await obsidian_generator.generate_vault()
        knowledge_dir = vault_dir / "Knowledge"
        notes = list(knowledge_dir.glob("*.md"))
        assert len(notes) > 0  # Should have seeded knowledge

    @pytest.mark.asyncio
    async def test_export_as_zip(self, obsidian_generator: ObsidianVaultGenerator):
        zip_path = await obsidian_generator.export_as_zip()
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"

        # Verify ZIP contents
        with zipfile.ZipFile(str(zip_path), "r") as zf:
            names = zf.namelist()
            assert any("mercatus-vault" in n for n in names)
            assert any(".obsidian" in n for n in names)

    @pytest.mark.asyncio
    async def test_sync_vault(self, obsidian_generator: ObsidianVaultGenerator):
        stats = await obsidian_generator.sync_vault()
        assert "vault_path" in stats
        assert "total_notes" in stats
        assert stats["total_notes"] > 0

    @pytest.mark.asyncio
    async def test_markdown_has_frontmatter(self, obsidian_generator: ObsidianVaultGenerator):
        vault_dir = await obsidian_generator.generate_vault()
        knowledge_dir = vault_dir / "Knowledge"
        notes = list(knowledge_dir.glob("*.md"))
        if notes:
            content = notes[0].read_text(encoding="utf-8")
            assert content.startswith("---")
            assert "type:" in content

    @pytest.mark.asyncio
    async def test_markdown_has_wikilinks(self, obsidian_generator: ObsidianVaultGenerator):
        vault_dir = await obsidian_generator.generate_vault()
        index_path = vault_dir / "Index.md"
        content = index_path.read_text(encoding="utf-8")
        # Index should have wikilinks
        assert "[[" in content

    def test_sanitize_filename(self):
        assert ObsidianVaultGenerator._sanitize_filename("test file.md") == "test file.md"
        assert ObsidianVaultGenerator._sanitize_filename("test/file.md") == "test_file.md"
        assert ObsidianVaultGenerator._sanitize_filename("test<>file.md") == "test__file.md"
        assert ObsidianVaultGenerator._sanitize_filename("") == "untitled"
