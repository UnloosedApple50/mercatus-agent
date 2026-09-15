"""Brain Map — Knowledge Graph Visualization Engine."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from mercatus.db.database import Database, db
from mercatus.utils.logger import get_logger

logger = get_logger("brain")


@dataclass
class GraphNode:
    """A node in the knowledge graph."""
    id: str
    label: str
    type: str  # episodic, semantic, decision, knowledge, conversation
    module: str
    size: int = 10
    color: str = "#6366f1"
    metadata: dict[str, Any] = field(default_factory=dict)

    TYPE_COLORS = {
        "episodic": "#3b82f6",  # Blue
        "semantic": "#10b981",  # Green
        "decision": "#f59e0b",  # Gold
        "knowledge": "#8b5cf6",  # Purple
        "conversation": "#6b7280",  # Gray
    }

    def __post_init__(self) -> None:
        self.color = self.TYPE_COLORS.get(self.type, "#6366f1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "module": self.module,
            "size": self.size,
            "color": self.color,
            "metadata": self.metadata,
        }


@dataclass
class GraphEdge:
    """An edge connecting two nodes."""
    source: str
    target: str
    label: str = ""
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.source,
            "to": self.target,
            "label": self.label,
            "weight": self.weight,
        }


@dataclass
class KnowledgeGraph:
    """Complete knowledge graph."""
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }


class BrainMapEngine:
    """Generates knowledge graph from agent data."""

    def __init__(self, database: Database | None = None) -> None:
        self._db = database or db

    async def generate_graph(
        self,
        module_filter: str | None = None,
        type_filter: list[str] | None = None,
        limit: int = 200,
    ) -> KnowledgeGraph:
        """Generate the full knowledge graph."""
        graph = KnowledgeGraph()

        # Add episodic memory nodes
        if not type_filter or "episodic" in type_filter:
            await self._add_episodic_nodes(graph, module_filter, limit // 4)

        # Add semantic memory nodes
        if not type_filter or "semantic" in type_filter:
            await self._add_semantic_nodes(graph, module_filter, limit // 4)

        # Add decision nodes
        if not type_filter or "decision" in type_filter:
            await self._add_decision_nodes(graph, module_filter, limit // 4)

        # Add conversation nodes
        if not type_filter or "conversation" in type_filter:
            await self._add_conversation_nodes(graph, module_filter, limit // 4)

        # Create edges
        await self._create_edges(graph)

        return graph

    async def _add_episodic_nodes(
        self,
        graph: KnowledgeGraph,
        module_filter: str | None,
        limit: int,
    ) -> None:
        """Add episodic memory nodes."""
        query = "SELECT * FROM episodic_memory"
        params: list[Any] = []

        if module_filter:
            query += " WHERE module = ?"
            params.append(module_filter)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = await self._db.fetchall(query, tuple(params) if params else None)

        for row in rows:
            sid = row["session_id"] if isinstance(row["session_id"], str) else row[1]
            module = row["module"] if isinstance(row["module"], str) else row[2]
            query_text = row["query"] if isinstance(row["query"], str) else row[3]
            created = row["created_at"] if isinstance(row["created_at"], str) else row[7]

            label = query_text[:50] + "..." if len(query_text) > 50 else query_text

            node = GraphNode(
                id=f"epi_{sid}_{row['id'] if isinstance(row['id'], int) else row[0]}",
                label=label,
                type="episodic",
                module=module,
                size=8,
                metadata={
                    "session_id": sid,
                    "query": query_text[:200],
                    "created_at": created,
                },
            )
            graph.nodes.append(node)

    async def _add_semantic_nodes(
        self,
        graph: KnowledgeGraph,
        module_filter: str | None,
        limit: int,
    ) -> None:
        """Add semantic memory nodes."""
        query = "SELECT * FROM semantic_memory"
        params: list[Any] = []

        if module_filter:
            query += " WHERE module = ?"
            params.append(module_filter)

        query += " ORDER BY use_count DESC LIMIT ?"
        params.append(limit)

        rows = await self._db.fetchall(query, tuple(params) if params else None)

        for row in rows:
            module = row["module"] if isinstance(row["module"], str) else row[1]
            key = row["key"] if isinstance(row["key"], str) else row[3]
            value = row["value"] if isinstance(row["value"], str) else row[4]
            use_count = row["use_count"] if isinstance(row["use_count"], int) else row[7]

            node = GraphNode(
                id=f"sem_{row['id'] if isinstance(row['id'], int) else row[0]}",
                label=key.replace("_", " ").title(),
                type="semantic",
                module=module,
                size=min(15, 8 + use_count),
                metadata={
                    "key": key,
                    "value": value[:200],
                    "category": row["category"] if isinstance(row["category"], str) else row[2],
                    "use_count": use_count,
                },
            )
            graph.nodes.append(node)

    async def _add_decision_nodes(
        self,
        graph: KnowledgeGraph,
        module_filter: str | None,
        limit: int,
    ) -> None:
        """Add decision nodes."""
        query = "SELECT * FROM decisions"
        params: list[Any] = []

        if module_filter:
            query += " WHERE module = ?"
            params.append(module_filter)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = await self._db.fetchall(query, tuple(params) if params else None)

        for row in rows:
            module = row["module"] if isinstance(row["module"], str) else row[2]
            context = row["context"] if isinstance(row["context"], str) else row[3]
            selected = row["selected_option"] if isinstance(row["selected_option"], str) else row[5]

            label = (selected or context[:40]) + "..." if len(selected or context) > 40 else (selected or context)

            node = GraphNode(
                id=f"dec_{row['id'] if isinstance(row['id'], int) else row[0]}",
                label=label,
                type="decision",
                module=module,
                size=12,
                metadata={
                    "context": context[:200],
                    "selected_option": selected,
                    "confidence": row["confidence"] if isinstance(row["confidence"], float) else row[6],
                },
            )
            graph.nodes.append(node)

    async def _add_conversation_nodes(
        self,
        graph: KnowledgeGraph,
        module_filter: str | None,
        limit: int,
    ) -> None:
        """Add conversation (session) nodes."""
        query = "SELECT * FROM sessions"
        params: list[Any] = []

        if module_filter:
            query += " WHERE module = ?"
            params.append(module_filter)

        query += " ORDER BY last_active DESC LIMIT ?"
        params.append(limit)

        rows = await self._db.fetchall(query, tuple(params) if params else None)

        for row in rows:
            sid = row["id"] if isinstance(row["id"], str) else row[0]
            module = row["module"] if isinstance(row["module"], str) else row[1]
            msg_count = row["message_count"] if isinstance(row["message_count"], int) else row[2]

            node = GraphNode(
                id=f"conv_{sid}",
                label=f"Session {sid[-6:]}",
                type="conversation",
                module=module,
                size=min(20, 10 + msg_count),
                metadata={
                    "session_id": sid,
                    "message_count": msg_count,
                    "started_at": row["started_at"] if isinstance(row["started_at"], str) else row[3],
                },
            )
            graph.nodes.append(node)

    async def _create_edges(self, graph: KnowledgeGraph) -> None:
        """Create edges between related nodes."""
        nodes_by_id = {n.id: n for n in graph.nodes}
        nodes_by_module: dict[str, list[GraphNode]] = {}

        for node in graph.nodes:
            if node.module not in nodes_by_module:
                nodes_by_module[node.module] = []
            nodes_by_module[node.module].append(node)

        # Connect nodes within same module
        for module, nodes in nodes_by_module.items():
            for i, node in enumerate(nodes):
                # Connect to next 2 nodes in same module
                for j in range(i + 1, min(i + 3, len(nodes))):
                    edge = GraphEdge(
                        source=node.id,
                        target=nodes[j].id,
                        label=module,
                        weight=0.5,
                    )
                    graph.edges.append(edge)

        # Connect episodic to conversation nodes by session
        epi_nodes = [n for n in graph.nodes if n.type == "episodic"]
        conv_nodes = {n.metadata.get("session_id", ""): n for n in graph.nodes if n.type == "conversation"}

        for epi in epi_nodes:
            sid = epi.metadata.get("session_id", "")
            if sid in conv_nodes:
                edge = GraphEdge(
                    source=epi.id,
                    target=conv_nodes[sid].id,
                    label="part_of",
                    weight=1.0,
                )
                graph.edges.append(edge)

        # Connect semantic nodes by shared tags/keywords
        sem_nodes = [n for n in graph.nodes if n.type == "semantic"]
        for i, node in enumerate(sem_nodes):
            node_keywords = set(self._extract_keywords(node.label))
            for j in range(i + 1, min(i + 5, len(sem_nodes))):
                other_keywords = set(self._extract_keywords(sem_nodes[j].label))
                overlap = node_keywords & other_keywords
                if overlap:
                    edge = GraphEdge(
                        source=node.id,
                        target=sem_nodes[j].id,
                        label="related",
                        weight=len(overlap) * 0.3,
                    )
                    graph.edges.append(edge)

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text."""
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        stop_words = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her", "was"}
        return [w for w in words if w not in stop_words]

    async def get_node_details(self, node_id: str) -> dict[str, Any] | None:
        """Get detailed information about a specific node."""
        # Determine type from prefix
        if node_id.startswith("epi_"):
            return await self._get_episodic_details(node_id)
        elif node_id.startswith("sem_"):
            return await self._get_semantic_details(node_id)
        elif node_id.startswith("dec_"):
            return await self._get_decision_details(node_id)
        elif node_id.startswith("conv_"):
            return await self._get_conversation_details(node_id)
        return None

    async def _get_episodic_details(self, node_id: str) -> dict[str, Any] | None:
        """Get episodic memory details."""
        try:
            mem_id = int(node_id.split("_")[-1])
        except (ValueError, IndexError):
            return None

        row = await self._db.fetchone(
            "SELECT * FROM episodic_memory WHERE id = ?",
            (mem_id,),
        )
        if not row:
            return None

        return {
            "id": node_id,
            "type": "episodic",
            "session_id": row["session_id"] if isinstance(row["session_id"], str) else row[1],
            "module": row["module"] if isinstance(row["module"], str) else row[2],
            "query": row["query"] if isinstance(row["query"], str) else row[3],
            "response": row["response"] if isinstance(row["response"], str) else row[4],
            "confidence": row["confidence"] if isinstance(row["confidence"], float) else row[5],
            "outcome": row["outcome"] if isinstance(row["outcome"], str) else row[6],
            "created_at": row["created_at"] if isinstance(row["created_at"], str) else row[7],
        }

    async def _get_semantic_details(self, node_id: str) -> dict[str, Any] | None:
        """Get semantic memory details."""
        try:
            mem_id = int(node_id.split("_")[-1])
        except (ValueError, IndexError):
            return None

        row = await self._db.fetchone(
            "SELECT * FROM semantic_memory WHERE id = ?",
            (mem_id,),
        )
        if not row:
            return None

        return {
            "id": node_id,
            "type": "semantic",
            "module": row["module"] if isinstance(row["module"], str) else row[1],
            "category": row["category"] if isinstance(row["category"], str) else row[2],
            "key": row["key"] if isinstance(row["key"], str) else row[3],
            "value": row["value"] if isinstance(row["value"], str) else row[4],
            "confidence": row["confidence"] if isinstance(row["confidence"], float) else row[5],
            "use_count": row["use_count"] if isinstance(row["use_count"], int) else row[7],
        }

    async def _get_decision_details(self, node_id: str) -> dict[str, Any] | None:
        """Get decision details."""
        try:
            dec_id = int(node_id.split("_")[-1])
        except (ValueError, IndexError):
            return None

        row = await self._db.fetchone(
            "SELECT * FROM decisions WHERE id = ?",
            (dec_id,),
        )
        if not row:
            return None

        return {
            "id": node_id,
            "type": "decision",
            "module": row["module"] if isinstance(row["module"], str) else row[2],
            "context": row["context"] if isinstance(row["context"], str) else row[3],
            "selected_option": row["selected_option"] if isinstance(row["selected_option"], str) else row[5],
            "confidence": row["confidence"] if isinstance(row["confidence"], float) else row[6],
            "reasoning": row["reasoning"] if isinstance(row["reasoning"], str) else row[7],
        }

    async def _get_conversation_details(self, node_id: str) -> dict[str, Any] | None:
        """Get conversation (session) details."""
        sid = node_id.replace("conv_", "")

        row = await self._db.fetchone(
            "SELECT * FROM sessions WHERE id = ?",
            (sid,),
        )
        if not row:
            return None

        # Get messages
        messages = await self._db.fetchall(
            "SELECT * FROM episodic_memory WHERE session_id = ? ORDER BY created_at LIMIT 10",
            (sid,),
        )

        return {
            "id": node_id,
            "type": "conversation",
            "session_id": sid,
            "module": row["module"] if isinstance(row["module"], str) else row[1],
            "message_count": row["message_count"] if isinstance(row["message_count"], int) else row[2],
            "started_at": row["started_at"] if isinstance(row["started_at"], str) else row[3],
            "last_active": row["last_active"] if isinstance(row["last_active"], str) else row[4],
            "recent_messages": [
                {
                    "query": m["query"] if isinstance(m["query"], str) else m[3],
                    "response": (m["response"] if isinstance(m["response"], str) else m[4])[:100],
                }
                for m in messages
            ],
        }


brain_engine = BrainMapEngine()
