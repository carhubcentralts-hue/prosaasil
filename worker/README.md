# ⚠️ DEPRECATED - DO NOT USE

This directory contains an **obsolete** worker setup and should **NOT** be used.

## Why is this deprecated?

This directory contains an old standalone RQ worker implementation that:
- Runs `python -m rq worker default` 
- Uses a separate Dockerfile
- Is NOT integrated with the main application

## What should you use instead?

**Use the correct worker:** `server/worker.py`

This is started automatically by docker-compose.yml:
```yaml
worker:
  command: ["python", "-m", "server.worker"]
```

## Why keep this directory?

This directory is kept for historical reference only. It may be safely deleted in the future once we confirm no external scripts reference it.

## Migration Notes

The correct worker configuration:
- **File**: `server/worker.py`
- **Command**: `python -m server.worker`
- **Docker**: Uses `Dockerfile.backend` (same as API)
- **Config**: Defined in `docker-compose.yml` service `worker`

Do **NOT** use anything from this `worker/` directory.
