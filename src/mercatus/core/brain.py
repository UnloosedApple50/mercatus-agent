"""Brain Map — knowledge graph generation from agent memory/decisions/knowledge."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from mercatus.db.database import Database
from mercatus.utils.logger import get_logger

logger = get_logger("brain")


@dataclass
class BrainNode:
    """A node in the knowledge graph."""
    id: str
    label: str
    type: str  # memory, decision, knowledge, conversation
    size: float = 1.0
    color: str = "#6366f1"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "size": self.size,
            "color": self.color,
            "metadata": self.metadata,
        }


@dataclass
class BrainEdge:
    """An edge connecting two nodes."""
    source: str
    target: str
    label: str = ""
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "weight": self.weight,
        }


@dataclass
class BrainGraph:
    """Complete brain graph with nodes and edges."""
    nodes: list[BrainNode] = field(default_factory=list)
    edges: list[BrainEdge] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }


# Color coding by node type
NODE_COLORS = {
    "memory": "#6366f1",       # Indigo
    "decision": "#f59e0b",     # Amber
    "knowledge": "#10b981",    # Emerald
    "conversation": "#3b82f6", # Blue
    "session": "#8b5cf6",      # Violet
}

# Node type sizes (base)
NODE_SIZES = {
    "memory": 8.0,
    "decision": 10.0,
    "knowledge": 12.0,
    "conversation": 6.0,
    "session": 14.0,
}


class BrainMapGenerator:
    """Generates knowledge graph data from Mercatus memory stores."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def generate_graph(
        self,
        module: Optional[str] = None,
        limit: int = 200,
    ) -> BrainGraph:
        """
        Generate the complete brain graph.

        Args:
            module: Optional module filter.
            limit: Maximum nodes per type.

        Returns:
            BrainGraph with nodes and edges.
        """
        graph = BrainGraph()

        # Add knowledge nodes
        await self._add_knowledge_nodes(graph, module, limit)

        # Add decision nodes
        await self._add_decision_nodes(graph, module, limit)

        # Add episodic memory nodes
        await self._add_memory_nodes(graph, module, limit)

        # Add session nodes
        await self._add_session_nodes(graph, module, limit)

        # Add conversation nodes (aggregated episodic per session)
        await self._add_conversation_nodes(graph, module, limit)

        # Detect relationships (edges)
        await self._detect_relationships(graph)

        return graph

    async def get_node_details(self, node_id: str) -> dict[str, Any]:
        """
        Get details for a specific node.

        Args:
            node_id: Node identifier (e.g., 'knowledge_42', 'decision_7').

        Returns:
            Node details with relationships.
        """
        parts = node_id.split("_", 1)
        if len(parts) != 2:
            return {"error": "Invalid node ID"}

        node_type, entity_id = parts[0], parts[1]

        if node_type == "knowledge":
            return await self._get_knowledge_details(int(entity_id))
        elif node_type == "decision":
            return await self._get_decision_details(int(entity_id))
        elif node_type == "memory":
            return await self._get_memory_details(int(entity_id))
        elif node_type == "session":
            return await self._get_session_details(entity_id)
        elif node_type == "conversation":
            return await self._get_conversation_details(entity_id)

        return {"error": "Unknown node type"}

    async def _add_knowledge_nodes(
        self,
        graph: BrainGraph,
        module: Optional[str],
        limit: int,
    ) -> None:
        """Add semantic knowledge nodes."""
        query = "SELECT * FROM semantic_memory"
        params: list[Any] = []

        if module:
            query += " WHERE module = ?"
            params.append(module)

        query += " ORDER BY use_count DESC LIMIT ?"
        params.append(limit)

        rows = await self._db.fetchall(query, tuple(params))

        for row in rows:
            use_count = row[8] if isinstance(row[8], int) else row["use_count"]
            confidence = row[5] if isinstance(row[5], float) else row["confidence"]
            size = NODE_SIZES["knowledge"] + (use_count * 0.5) + (confidence * 3)

            graph.nodes.append(BrainNode(
                id=f"knowledge_{row[0] if isinstance(row[0], int) else row['id']}",
                label=row[3] if isinstance(row[3], str) else row["key"],
                type="knowledge",
                size=min(size, 25.0),
                color=NODE_COLORS["knowledge"],
                metadata={
                    "module": row[1] if isinstance(row[1], str) else row["module"],
                    "category": row[2] if isinstance(row[2], str) else row["category"],
                    "value": (row[4] if isinstance(row[4], str) else row["value"])[:200],
                    "confidence": confidence,
                    "use_count": use_count,
                },
            ))

    async def _add_decision_nodes(
        self,
        graph: BrainGraph,
        module: Optional[str],
        limit: int,
    ) -> None:
        """Add decision nodes."""
        query = "SELECT * FROM decisions"
        params: list[Any] = []

        if module:
            query += " WHERE module = ?"
            params.append(module)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = await self._db.fetchall(query, tuple(params))

        for row in rows:
            confidence = row[5] if isinstance(row[5], float) else row["confidence"]
            size = NODE_SIZES["decision"] + (confidence * 5)

            graph.nodes.append(BrainNode(
                id=f"decision_{row[0] if isinstance(row[0], int) else row['id']}",
                label=(row[3] if isinstance(row[3], str) else row["context"])[:60],
                type="decision",
                size=min(size, 20.0),
                color=NODE_COLORS["decision"],
                metadata={
                    "module": row[2] if isinstance(row[2], str) else row["module"],
                    "context": (row[3] if isinstance(row[3], str) else row["context"])[:200],
                    "selected_option": row[5] if isinstance(row[5], str) else row["selected_option"],
                    "confidence": confidence,
                    "outcome": row[7] if isinstance(row[7], str) else row["outcome"],
                },
            ))

    async def _add_memory_nodes(
        self,
        graph: BrainGraph,
        module: Optional[str],
        limit: int,
    ) -> None:
        """Add episodic memory nodes."""
        query = "SELECT * FROM episodic_memory"
        params: list[Any] = []

        if module:
            query += " WHERE module = ?"
            params.append(module)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = await self._db.fetchall(query, tuple(params))

        for row in rows:
            confidence = row[5] if isinstance(row[5], float) else row["confidence"]
            size = NODE_SIZES["memory"] + (confidence * 3)

            graph.nodes.append(BrainNode(
                id=f"memory_{row[0] if isinstance(row[0], int) else row['id']}",
                label=(row[3] if isinstance(row[3], str) else row["query"])[:60],
                type="memory",
                size=min(size, 15.0),
                color=NODE_COLORS["memory"],
                metadata={
                    "module": row[2] if isinstance(row[2], str) else row["module"],
                    "query": (row[3] if isinstance(row[3], str) else row["query"])[:200],
                    "response": (row[4] if isinstance(row[4], str) else row["response"])[:200],
                    "confidence": confidence,
                    "outcome": row[6] if isinstance(row[6], str) else row["outcome"],
                },
            ))

    async def _add_session_nodes(
        self,
        graph: BrainGraph,
        module: Optional[str],
        limit: int,
    ) -> None:
        """Add session nodes."""
        query = "SELECT * FROM sessions"
        params: list[Any] = []

        if module:
            query += " WHERE module = ?"
            params.append(module)

        query += " ORDER BY last_active DESC LIMIT ?"
        params.append(limit)

        rows = await self._db.fetchall(query, tuple(params))

        for row in rows:
            msg_count = row[2] if isinstance(row[2], int) else row["message_count"]
            size = NODE_SIZES["session"] + (msg_count * 0.3)

            graph.nodes.append(BrainNode(
                id=f"session_{row[0] if isinstance(row[0], str) else row['id']}",
                label=f"Session {row[0] if isinstance(row[0], str) else row['id'][:8]}",
                type="session",
                size=min(size, 30.0),
                color=NODE_COLORS["session"],
                metadata={
                    "module": row[1] if isinstance(row[1], str) else row["module"],
                    "message_count": msg_count,
                    "started_at": row[3] if isinstance(row[3], str) else row["started_at"],
                    "last_active": row[4] if isinstance(row[4], str) else row["last_active"],
                },
            ))

    async def _add_conversation_nodes(
        self,
        graph: BrainGraph,
        module: Optional[str],
        limit: int,
    ) -> None:
        """Add conversation nodes (aggregated per session)."""
        query = """
            SELECT session_id, module, COUNT(*) as msg_count,
                   AVG(confidence) as avg_conf,
                   MAX(created_at) as last_msg
            FROM episodic_memory
            WHERE session_id IS NOT NULL
        """
        params: list[Any] = []

        if module:
            query += " AND module = ?"
            params.append(module)

        query += " GROUP BY session_id ORDER BY last_msg DESC LIMIT ?"
        params.append(limit)

        try:
            rows = await self._db.fetchall(query, tuple(params))
            for row in rows:
                session_id = row[0] if isinstance(row[0], str) else row["session_id"]
                msg_count = row[2] if isinstance(row[2], int) else row["msg_count"]
                avg_conf = row[3] if isinstance(row[3], (int, float)) else row["avg_conf"]
                size = NODE_SIZES["conversation"] + (msg_count * 0.5) + (float(avg_conf or 0) * 3)

                graph.nodes.append(BrainNode(
                    id=f"conversation_{session_id}",
                    label=f"Conv {session_id[:8]}",
                    type="conversation",
                    size=min(size, 20.0),
                    color=NODE_COLORS["conversation"],
                    metadata={
                        "session_id": session_id,
                        "module": row[1] if isinstance(row[1], str) else row["module"],
                        "message_count": msg_count,
                        "avg_confidence": float(avg_conf or 0),
                    },
                ))
        except Exception as e:
            logger.warning(f"Failed to add conversation nodes: {e}")

    async def _detect_relationships(self, graph: BrainGraph) -> None:
        """Detect relationships between nodes and create edges."""
        nodes_by_type: dict[str, list[BrainNode]] = {}
        for node in graph.nodes:
            nodes_by_type.setdefault(node.type, []).append(node)

        # Same-module connections
        for node in graph.nodes:
            node_module = node.metadata.get("module", "general")

            # Connect knowledge nodes in same category
            if node.type == "knowledge":
                for other in nodes_by_type.get("knowledge", []):
                    if other.id <= node.id:
                        continue
                    if (other.metadata.get("category") == node.metadata.get("category")
                            and other.id != node.id):
                        graph.edges.append(BrainEdge(
                            source=node.id,
                            target=other.id,
                            label="same_category",
                            weight=0.5,
                        ))

            # Connect decisions to knowledge in same module
            if node.type == "decision":
                for other in nodes_by_type.get("knowledge", []):
                    if other.metadata.get("module") == node_module:
                        graph.edges.append(BrainEdge(
                            source=node.id,
                            target=other.id,
                            label="informed_by",
                            weight=0.7,
                        ))

            # Connect memories to sessions
            if node.type == "memory":
                session_id = node.metadata.get("session_id", "")
                conversation_node = f"conversation_{session_id}"
                if any(n.id == conversation_node for n in graph.nodes):
                    graph.edges.append(BrainEdge(
                        source=node.id,
                        target=conversation_node,
                        label="part_of",
                        weight=0.9,
                    ))

        # Session-to-conversation edges
        for node in graph.nodes:
            if node.type == "session":
                session_id = node.metadata.get("session_id", node.id.replace("session_", ""))
                conversation_node = f"conversation_{session_id}"
                if any(n.id == conversation_node for n in graph.nodes):
                    graph.edges.append(BrainEdge(
                        source=node.id,
                        target=conversation_node,
                        label="aggregates",
                        weight=0.8,
                    ))

        # Cross-module connections (knowledge sharing same tags)
        knowledge_nodes = nodes_by_type.get("knowledge", [])
        for i, node in enumerate(knowledge_nodes):
            for other in knowledge_nodes[i + 1:]:
                if node.metadata.get("module") != other.metadata.get("module"):
                    # Connect cross-module knowledge
                    graph.edges.append(BrainEdge(
                        source=node.id,
                        target=other.id,
                        label="cross_module",
                        weight=0.3,
                    ))

    async def _get_knowledge_details(self, knowledge_id: int) -> dict[str, Any]:
        """Get details for a knowledge node."""
        row = await self._db.fetchone(
            "SELECT * FROM semantic_memory WHERE id = ?",
            (knowledge_id,),
        )
        if not row:
            return {"error": "Knowledge not found"}

        return {
            "id": f"knowledge_{knowledge_id}",
            "type": "knowledge",
            "module": row[1] if isinstance(row[1], str) else row["module"],
            "category": row[2] if isinstance(row[2], str) else row["category"],
            "key": row[3] if isinstance(row[3], str) else row["key"],
            "value": row[4] if isinstance(row[4], str) else row["value"],
            "confidence": row[5] if isinstance(row[5], float) else row["confidence"],
            "source": row[6] if isinstance(row[6], str) else row["source"],
            "tags": json.loads(row[7]) if isinstance(row[7], str) and row[7] else [],
            "use_count": row[8] if isinstance(row[8], int) else row["use_count"],
            "relationships": await self._find_related_nodes(f"knowledge_{knowledge_id}"),
        }

    async def _get_decision_details(self, decision_id: int) -> dict[str, Any]:
        """Get details for a decision node."""
        row = await self._db.fetchone(
            "SELECT * FROM decisions WHERE id = ?",
            (decision_id,),
        )
        if not row:
            return {"error": "Decision not found"}

        return {
            "id": f"decision_{decision_id}",
            "type": "decision",
            "session_id": row[1] if isinstance(row[1], str) else row["session_id"],
            "module": row[2] if isinstance(row[2], str) else row["module"],
            "context": row[3] if isinstance(row[3], str) else row["context"],
            "options": json.loads(row[4]) if isinstance(row[4], str) and row[4] else [],
            "selected_option": row[5] if isinstance(row[5], str) else row["selected_option"],
            "confidence": row[5] if isinstance(row[5], float) else row["confidence"],
            "reasoning": row[6] if isinstance(row[6], str) else row["reasoning"],
            "outcome": row[7] if isinstance(row[7], str) else row["outcome"],
            "created_at": row[8] if isinstance(row[8], str) else row["created_at"],
            "relationships": await self._find_related_nodes(f"decision_{decision_id}"),
        }

    async def _get_memory_details(self, memory_id: int) -> dict[str, Any]:
        """Get details for a memory node."""
        row = await self._db.fetchone(
            "SELECT * FROM episodic_memory WHERE id = ?",
            (memory_id,),
        )
        if not row:
            return {"error": "Memory not found"}

        metadata = json.loads(row[9]) if isinstance(row[9], str) and row[9] else {}

        return {
            "id": f"memory_{memory_id}",
            "type": "memory",
            "session_id": row[1] if isinstance(row[1], str) else row["session_id"],
            "module": row[2] if isinstance(row[2], str) else row["module"],
            "query": row[3] if isinstance(row[3], str) else row["query"],
            "response": row[4] if isinstance(row[4], str) else row["response"],
            "confidence": row[5] if isinstance(row[5], float) else row["confidence"],
            "outcome": row[6] if isinstance(row[6], str) else row["outcome"],
            "outcome_score": row[7] if isinstance(row[7], float) else row["outcome_score"],
            "metadata": metadata,
            "created_at": row[8] if isinstance(row[8], str) else row["created_at"],
            "relationships": await self._find_related_nodes(f"memory_{memory_id}"),
        }

    async def _get_session_details(self, session_id: str) -> dict[str, Any]:
        """Get details for a session node."""
        row = await self._db.fetchone(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        )
        if not row:
            return {"error": "Session not found"}

        # Get memories in this session
        memories = await self._db.fetchall(
            "SELECT id, query, confidence FROM episodic_memory WHERE session_id = ? ORDER BY created_at DESC LIMIT 20",
            (session_id,),
        )

        return {
            "id": f"session_{session_id}",
            "type": "session",
            "module": row[1] if isinstance(row[1], str) else row["module"],
            "message_count": row[2] if isinstance(row[2], int) else row["message_count"],
            "started_at": row[3] if isinstance(row[3], str) else row["started_at"],
            "last_active": row[4] if isinstance(row[4], str) else row["last_active"],
            "memories": [
                {
                    "id": f"memory_{m[0] if isinstance(m[0], int) else m['id']}",
                    "query": (m[1] if isinstance(m[1], str) else m["query"])[:100],
                    "confidence": m[2] if isinstance(m[2], float) else m["confidence"],
                }
                for m in memories
            ],
            "relationships": await self._find_related_nodes(f"session_{session_id}"),
        }

    async def _get_conversation_details(self, session_id: str) -> dict[str, Any]:
        """Get details for a conversation node."""
        memories = await self._db.fetchall(
            "SELECT id, query, response, confidence, created_at FROM episodic_memory WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        )

        return {
            "id": f"conversation_{session_id}",
            "type": "conversation",
            "session_id": session_id,
            "message_count": len(memories),
            "messages": [
                {
                    "id": f"memory_{m[0] if isinstance(m[0], int) else m['id']}",
                    "query": (m[1] if isinstance(m[1], str) else m["query"])[:150],
                    "response": (m[2] if isinstance(m[2], str) else m["response"])[:150],
                    "confidence": m[3] if isinstance(m[3], (int, float)) else m["confidence"],
                    "created_at": m[4] if isinstance(m[4], str) else m["created_at"],
                }
                for m in memories
            ],
            "relationships": await self._find_related_nodes(f"conversation_{session_id}"),
        }

    async def _find_related_nodes(self, node_id: str) -> list[dict[str, Any]]:
        """Find nodes related to the given node."""
        # Re-generate a small graph to find connections
        graph = await self._generate_subgraph(node_id)

        related = []
        for edge in graph.edges:
            if edge.source == node_id:
                target_node = next((n for n in graph.nodes if n.id == edge.target), None)
                if target_node:
                    related.append({
                        "node": target_node.to_dict(),
                        "relationship": edge.label,
                        "weight": edge.weight,
                    })
            elif edge.target == node_id:
                source_node = next((n for n in graph.nodes if n.id == edge.source), None)
                if source_node:
                    related.append({
                        "node": source_node.to_dict(),
                        "relationship": edge.label,
                        "weight": edge.weight,
                    })

        return related[:20]

    async def _generate_subgraph(self, center_node_id: str) -> BrainGraph:
        """Generate a small subgraph centered on a node."""
        graph = BrainGraph()

        parts = center_node_id.split("_", 1)
        if len(parts) != 2:
            return graph

        node_type = parts[0]

        # Add the center node
        if node_type == "knowledge":
            await self._add_knowledge_nodes(graph, None, 50)
        elif node_type == "decision":
            await self._add_decision_nodes(graph, None, 50)
        elif node_type == "memory":
            await self._add_memory_nodes(graph, None, 50)
        elif node_type == "session":
            await self._add_session_nodes(graph, None, 20)
        elif node_type == "conversation":
            await self._add_conversation_nodes(graph, None, 20)

        await self._detect_relationships(graph)
        return graph
