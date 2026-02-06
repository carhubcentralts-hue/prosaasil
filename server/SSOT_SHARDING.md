# Baileys WhatsApp Sharding — SSOT

## Overview

ProSaaS supports horizontal scaling of the Baileys WhatsApp service via tenant-based sharding. Each shard is an independent Baileys instance with its own auth state and connections.

## Architecture

```
┌────────────────┐     ┌─────────────────────┐
│  prosaas-api   │────▶│ whatsapp_shard_router│
│                │     │  get_baileys_base_url│
└────────────────┘     └──────┬──────┬───────┘
                              │      │
                   ┌──────────┘      └──────────┐
                   ▼                             ▼
           ┌──────────────┐              ┌──────────────┐
           │  baileys-1   │              │  baileys-2   │
           │  (shard 1)   │              │  (shard 2)   │
           │  port 3300   │              │  port 3300   │
           └──────────────┘              └──────────────┘
           volume:                       volume:
           whatsapp_auth                 whatsapp_auth_shard2
```

## Shard Assignment

Each `Business` row has a `whatsapp_shard` column (integer, default=1).

### Assignment Logic (`server/whatsapp_shard_router.py`)

1. If `business.whatsapp_shard` is set and > 0 → use that shard directly
2. Otherwise → `hash(business_id) % N_SHARDS + 1` (deterministic fallback)

### Shard URL Resolution

1. Check env `BAILEYS_SHARD_{N}_URL` (explicit override)
2. Fall back to Docker service name: `http://baileys-{N}:3300`
3. For single-shard mode: `http://baileys:3300` (backward compatible)

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BAILEYS_NUM_SHARDS` | `1` | Total number of Baileys shards |
| `BAILEYS_PORT` | `3300` | Port for all Baileys instances |
| `BAILEYS_SHARD_{N}_URL` | auto | Override URL for shard N |
| `BAILEYS_BASE_URL` | `http://baileys:3300` | Legacy single-shard URL |

### Docker Compose Activation

```bash
# Single shard (default — no change needed)
docker compose up -d

# Multi-shard (activate baileys-2)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile multi-shard up -d
```

### Adding More Shards

1. Add new service in `docker-compose.prod.yml`:
   ```yaml
   baileys-3:
     build: { context: ., dockerfile: Dockerfile.baileys }
     profiles: [multi-shard]
     environment:
       BAILEYS_SHARD_ID: "3"
     volumes:
       - whatsapp_auth_shard3:/app/storage/whatsapp
   ```
2. Add volume: `whatsapp_auth_shard3:`
3. Set `BAILEYS_NUM_SHARDS=3` in `.env`
4. Assign businesses: `UPDATE business SET whatsapp_shard = 3 WHERE id IN (...)`

## Database Schema

```sql
ALTER TABLE business ADD COLUMN whatsapp_shard INTEGER NOT NULL DEFAULT 1;
```

## Key Files

| File | Purpose |
|------|---------|
| `server/whatsapp_shard_router.py` | Routing logic (SSOT) |
| `server/models_sql.py` | `Business.whatsapp_shard` column |
| `docker-compose.prod.yml` | Shard service definitions |
| `server/SSOT_SHARDING.md` | This document |

## Migration

When migrating from single to multi-shard:
1. All existing businesses default to `whatsapp_shard = 1`
2. Gradually move businesses to new shards via admin UI or SQL
3. Auth state must be re-established (QR scan) on the new shard instance

## Monitoring

- Each shard has independent healthcheck: `GET /health`
- Monitor via: `curl http://baileys-{N}:3300/health`
- Session counts returned in health response
