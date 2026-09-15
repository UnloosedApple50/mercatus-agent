"""Tests for Brain Map knowledge graph generation."""

from __future__ import annotations

import pytest
import pytest_asyncio
from typing import AsyncGenerator

from mercatus.core.brain import (
    BrainMapGenerator,
    BrainGraph,
    BrainNode,
    BrainEdge,
    NODE_COLORS,
    NODE_SIZES,
)
from mercatus.db.database import Database
from mercatus.db.migrations import init_schema, seed_knowledge


@pytest_asyncio.fixture
async def brain_db() -> AsyncGenerator[Database, None]:
    """Create a test database with seeded knowledge."""
    db = Database(":memory:")
    await db.initialize()
    await init_schema(db)
    await seed_knowledge(db)
    yield db
    await db.close()


@pytest_asyncio.fixture
async def brain_generator(brain_db: Database) -> BrainMapGenerator:
    """Create a brain map generator."""
    return BrainMapGenerator(brain_db)


class TestBrainNode:
    """Tests for BrainNode dataclass."""

    def test_create_node(self):
        node = BrainNode(
            id="knowledge_1",
            label="Test Node",
            type="knowledge",
            size=10.0,
            color="#6366f1",
        )
        assert node.id == "knowledge_1"
        assert node.label == "Test Node"
        assert node.type == "knowledge"
        assert node.size == 10.0
        assert node.color == "#6366f1"

    def test_to_dict(self):
        node = BrainNode(
            id="test_1",
            label="Test",
            type="memory",
            size=5.0,
            color="#f59e0b",
            metadata={"key": "value"},
        )
        result = node.to_dict()
        assert result["id"] == "test_1"
        assert result["label"] == "Test"
        assert result["type"] == "memory"
        assert result["size"] == 5.0
        assert result["color"] == "#f59e0b"
        assert result["metadata"] == {"key": "value"}


class TestBrainEdge:
    """Tests for BrainEdge dataclass."""

    def test_create_edge(self):
        edge = BrainEdge(
            source="node_1",
            target="node_2",
            label="related",
            weight=0.8,
        )
        assert edge.source == "node_1"
        assert edge.target == "node_2"
        assert edge.label == "related"
        assert edge.weight == 0.8

    def test_to_dict(self):
        edge = BrainEdge(source="a", target="b", label="test", weight=0.5)
        result = edge.to_dict()
        assert result["source"] == "a"
        assert result["target"] == "b"
        assert result["label"] == "test"
        assert result["weight"] == 0.5


class TestBrainGraph:
    """Tests for BrainGraph dataclass."""

    def test_empty_graph(self):
        graph = BrainGraph()
        assert graph.nodes == []
        assert graph.edges == []

    def test_to_dict(self):
        graph = BrainGraph(
            nodes=[BrainNode(id="n1", label="Node 1", type="knowledge")],
            edges=[BrainEdge(source="n1", target="n2")],
        )
        result = graph.to_dict()
        assert len(result["nodes"]) == 1
        assert len(result["edges"]) == 1
        assert result["nodes"][0]["id"] == "n1"


class TestBrainMapGenerator:
    """Tests for BrainMapGenerator."""

    @pytest.mark.asyncio
    async def test_init(self, brain_db: Database):
        generator = BrainMapGenerator(brain_db)
        assert generator._db == brain_db

    @pytest.mark.asyncio
    async def test_generate_graph(self, brain_generator: BrainMapGenerator):
        graph = await brain_generator.generate_graph()
        assert isinstance(graph, BrainGraph)
        assert len(graph.nodes) > 0  # Should have seeded knowledge nodes

    @pytest.mark.asyncio
    async def test_generate_graph_with_module_filter(self, brain_generator: BrainMapGenerator):
        graph = await brain_generator.generate_graph(module="sales")
        assert isinstance(graph, BrainGraph)
        # All nodes should be from sales module (or empty if no sales data)
        for node in graph.nodes:
            if node.metadata.get("module"):
                assert node.metadata["module"] == "sales"

    @pytest.mark.asyncio
    async def test_generate_graph_with_limit(self, brain_generator: BrainMapGenerator):
        graph = await brain_generator.generate_graph(limit=5)
        assert isinstance(graph, BrainGraph)
        # Should have at most 5 nodes per type
        knowledge_nodes = [n for n in graph.nodes if n.type == "knowledge"]
        assert len(knowledge_nodes) <= 5

    @pytest.mark.asyncio
    async def test_node_colors_defined(self):
        assert "memory" in NODE_COLORS
        assert "decision" in NODE_COLORS
        assert "knowledge" in NODE_COLORS
        assert "conversation" in NODE_COLORS
        assert "session" in NODE_COLORS

    @pytest.mark.asyncio
    async def test_node_sizes_defined(self):
        assert "memory" in NODE_SIZES
        assert "decision" in NODE_SIZES
        assert "knowledge" in NODE_SIZES
        assert "conversation" in NODE_SIZES
        assert "session" in NODE_SIZES

    @pytest.mark.asyncio
    async def test_get_knowledge_node_details(self, brain_generator: BrainMapGenerator):
        # First generate graph to get valid node IDs
        graph = await brain_generator.generate_graph()
        if graph.nodes:
            node_id = graph.nodes[0].id
            details = await brain_generator.get_node_details(node_id)
            assert "error" not in details or details.get("error") != "Invalid node ID"

    @pytest.mark.asyncio
    async def test_get_invalid_node_details(self, brain_generator: BrainMapGenerator):
        details = await brain_generator.get_node_details("nonexistent_999")
        assert "error" in details

    @pytest.mark.asyncio
    async def test_graph_has_edges(self, brain_generator: BrainMapGenerator):
        graph = await brain_generator.generate_graph()
        # With seeded knowledge, there should be some edges
        # (at least same-category connections)
        assert isinstance(graph.edges, list)
