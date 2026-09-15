# Brain Map

The Brain Map provides an interactive knowledge graph visualization of all agent data.

## Features

- **Canvas-based rendering** — Smooth zoom, pan, and navigation
- **Force-directed layout** — Automatic node positioning
- **Color coding** by node type:
  - Blue: Memories
  - Amber: Decisions
  - Emerald: Knowledge
  - Indigo: Conversations
  - Violet: Sessions
- **Search and filter** by type
- **Click for details** — View node metadata and relationships

## Node Types

### Knowledge Nodes
- Semantic memory facts and rules
- Sized by use count and confidence
- Connected by category

### Decision Nodes
- Recorded decisions with context
- Sized by confidence
- Connected to knowledge nodes in same module

### Memory Nodes
- Episodic memory entries
- Sized by confidence
- Connected to conversation nodes

### Conversation Nodes
- Aggregated per-session interactions
- Sized by message count
- Connected to individual messages

### Session Nodes
- Session tracking nodes
- Sized by activity
- Connected to conversations

## API Endpoints

```
GET /api/v1/brain/graph
GET /api/v1/brain/node/{node_id}
```

## Interactions

- **Scroll**: Zoom in/out
- **Drag**: Pan the view
- **Click**: Select and view details
- **Double-click**: Center on node
- **Search**: Filter nodes by label
- **Filter**: Show only specific types
