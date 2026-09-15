# Changelog

All notable changes to Mercatus Agent will be documented in this file.

## [1.0.0] - 2026-09-15

### Added
- **Brain Map**: Interactive knowledge graph visualization with canvas-based rendering
  - Nodes for memories, decisions, knowledge, conversations, and sessions
  - Force-directed layout with zoom, pan, and search
  - Color-coded by node type with size by importance
  - Click for details and relationship exploration
- **Obsidian Integration**: Export agent data as Obsidian-compatible vault
  - YAML frontmatter on all notes
  - Wikilinks for cross-referencing
  - ZIP export with complete vault structure
  - Memory, Decisions, Knowledge, and Conversations folders
- **Internationalization (i18n)**: 15 language support
  - English, Portuguese, Spanish, French, German, Italian
  - Japanese, Korean, Chinese (Simplified), Russian
  - Arabic (RTL), Hindi, Dutch, Turkish, Polish
  - data-i18n attribute support for automatic translation
- **Dark/Light Theme Toggle**: CSS custom properties for theming
  - Dark: #0a0b0f background, #12141c surface
  - Light: #ffffff background, #f5f5f5 surface
  - localStorage persistence (mercatus_theme)
- **Security Hardening**:
  - Brute force protection (5 failed attempts → 15min lockout)
  - Session timeout (30 minutes inactivity)
  - IP blocking (configurable threshold)
  - Secure headers middleware (CSP, HSTS, X-Frame-Options)
  - API key rotation support (90-day interval)
- **New API Endpoints**:
  - GET /api/v1/analytics/conversations
  - GET /api/v1/analytics/memory
  - GET /api/v1/analytics/tokens
  - GET /api/v1/logs
  - POST /api/v1/settings/llm
  - POST /api/v1/settings/memory
  - POST /api/v1/database/vacuum
  - GET /api/v1/security/audit
  - GET /api/v1/security/sessions
  - POST /api/v1/backup/create
  - POST /api/v1/backup/restore
  - GET /api/v1/brain/graph
  - GET /api/v1/brain/node/{id}
  - GET /api/v1/obsidian/export
  - POST /api/v1/obsidian/sync
- **Dashboard SPA**: Complete rewrite with sidebar navigation
  - 12 pages: Dashboard, Chat, Memory, Decisions, Knowledge
  - Brain Map, Analytics, Integrations, Training, Logs
  - Security, Settings
  - Theme toggle and language selector in sidebar
  - Top bar with agent status and model name
- **Documentation**: 6 new docs files
  - docs/ANALYTICS.md
  - docs/SECURITY_HARDENING.md
  - docs/BACKUP_RESTORE.md
  - docs/BRAIN_MAP.md
  - docs/OBSIDIAN.md
  - docs/I18N.md

### Changed
- Renamed from Athena to Mercatus (zero traces remaining)
- Updated all test files with Mercatus names
- Enhanced security module with brute force, session, and IP blocking
- Updated CSS with light theme variables
- Updated dashboard.js with theme and language support

### Fixed
- All imports updated to use mercatus package name
- All tests updated for MercatusAgent class
