# ProSaaS Scaling Plan

## Overview

ProSaaS is designed for horizontal scaling across all critical services: WhatsApp messaging, background workers, and voice calls.

## 1. WhatsApp (Baileys) Sharding

### Strategy: Tenant-Based Sharding

Each Baileys instance (shard) handles a subset of businesses. Routing is deterministic.

| Component | Implementation |
|-----------|---------------|
| Shard assignment | `Business.whatsapp_shard` column |
| Routing | `server/whatsapp_shard_router.py` |
| Fallback | `hash(business_id) % N_SHARDS` |
| Auth isolation | Separate Docker volumes per shard |

### Scaling Steps

1. Add new shard service to `docker-compose.prod.yml`
2. Set `BAILEYS_NUM_SHARDS=N` in environment
3. Assign businesses to new shard via admin or migration
4. Businesses re-scan QR on new shard

### Capacity

| Shards | Est. Concurrent Sessions | Est. Messages/min |
|--------|--------------------------|-------------------|
| 1 | ~50 | ~500 |
| 2 | ~100 | ~1,000 |
| 5 | ~250 | ~2,500 |
| 10 | ~500 | ~5,000 |

## 2. Worker Scaling

### Strategy: Queue-Dedicated Workers

Workers are split by queue priority to prevent low-priority tasks from blocking critical operations.

| Worker | Queues | Purpose |
|--------|--------|---------|
| `worker-high` | high | Realtime: WhatsApp send, webhooks |
| `worker-default` | default, receipts, receipts_sync | Standard processing |
| `worker-low` | low, maintenance, broadcasts, media, recordings | Deferred tasks |

### Scaling Steps

```bash
# Activate multi-worker profile
docker compose --profile multi-worker up -d

# Or scale individual workers
docker compose up -d --scale worker=3
```

### SSOT

Queue definitions: `server/queues.py`

## 3. Calls Scaling

### Strategy: Stateless Calls + Redis State

Call session state is stored in Redis, allowing multiple calls service replicas behind nginx.

| Component | Implementation |
|-----------|---------------|
| State storage | Redis (keyed by `call_sid`) |
| Max concurrent | Redis atomic counter |
| Default limit | 50 concurrent calls |
| Graceful degradation | 503 rejection when at capacity |

### Scaling Steps

```bash
# Scale calls service
docker compose up -d --scale prosaas-calls=3
```

### Capacity

| Replicas | MAX_CONCURRENT_CALLS | Total Capacity |
|----------|---------------------|----------------|
| 1 | 50 | 50 calls |
| 3 | 50 | 50 calls (shared limit) |
| 3 | 150 | 150 calls |

Note: MAX_CONCURRENT_CALLS is a global limit across all replicas (enforced via Redis).

## 4. API Scaling

The API service (`prosaas-api`) is stateless and can be scaled directly:

```bash
docker compose up -d --scale prosaas-api=3
```

Nginx load-balances across replicas automatically via Docker DNS.

## 5. Database Scaling

| Tier | Strategy | Implementation |
|------|----------|---------------|
| Connection pooling | Supabase Pooler | `DATABASE_URL_POOLER` env var |
| Read replicas | Managed DB provider | Configure `DATABASE_URL_READ` |
| Indexes | Separate indexer service | `docker-compose.prod.yml` indexer |

## 6. Infrastructure Diagram

```
Internet
    │
    ▼
┌──────────────┐
│    Nginx     │
│ (SSL, LB)   │
└──────┬───────┘
       │
  ┌────┼────┬────────────┐
  ▼    ▼    ▼            ▼
 API  API  Calls    Frontend
 (1)  (2)  (1-N)    (static)
  │    │    │
  └────┼────┘
       ▼
   ┌──────┐
   │Redis │◀── Workers (high/default/low)
   └──┬───┘
      │
      ▼
  ┌────────┐    ┌──────────────┐
  │   DB   │    │ Baileys 1..N │
  │(Pooler)│    │ (WhatsApp)   │
  └────────┘    └──────────────┘
```
