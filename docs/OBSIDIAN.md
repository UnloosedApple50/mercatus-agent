# Obsidian Integration

Mercatus Agent can export all data as an Obsidian-compatible vault.

## Features

- **Markdown notes** with YAML frontmatter
- **Wikilinks** for cross-referencing
- **Graph view** compatible structure
- **ZIP export** for easy download
- **Auto-sync** regeneration

## Vault Structure

```
mercatus-vault/
├── .obsidian/
│   ├── app.json
│   ├── appearance.json
│   ├── core-plugins.json
│   └── graph.json
├── Index.md          # Map of Content (MOC)
├── Memory/           # Episodic memory notes
├── Decisions/        # Decision history notes
├── Knowledge/        # Knowledge base notes
└── Conversations/    # Conversation log notes
```

## Note Format

Each note includes YAML frontmatter:

```yaml
---
type: memory
module: sales
session: sess_abc123
confidence: 0.85
created: "2026-09-15T14:30:00"
tags: [memory, sales]
---
```

## Exporting

### Via Dashboard
1. Navigate to Integrations → Obsidian Vault
2. Click "Export Vault"
3. Download `mercatus-vault.zip`

### Via API

```bash
# Export as ZIP
curl -O http://localhost:8585/api/v1/obsidian/export

# Sync vault
curl -X POST http://localhost:8585/api/v1/obsidian/sync
```

## API Endpoints

```
GET /api/v1/obsidian/export
POST /api/v1/obsidian/sync
```
