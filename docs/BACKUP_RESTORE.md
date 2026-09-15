# Backup & Restore

Mercatus Agent supports database backup and restore operations.

## Creating Backups

```bash
# Via API
curl -X POST http://localhost:8585/api/v1/backup/create

# Via CLI
python -m mercatus db init
```

## Backup Location

Backups are stored in `./backups/` with timestamped filenames:
- `mercatus_backup_20260915_143022.db`

## Restore Process

1. Stop the server
2. Replace the database file with the backup
3. Restart the server

## WAL Mode

SQLite WAL mode ensures:
- Crash safety without data loss
- Concurrent reads during writes
- Automatic checkpointing

## Database Vacuum

Reclaim disk space by vacuuming the database:

```bash
curl -X POST http://localhost:8585/api/v1/database/vacuum
```

## API Endpoints

```
POST /api/v1/backup/create
POST /api/v1/backup/restore
POST /api/v1/database/vacuum
```
