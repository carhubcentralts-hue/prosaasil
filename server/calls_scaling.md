# Calls Service Scaling Strategy

## Current Architecture

The calls service (`prosaas-calls`) handles WebSocket connections for Twilio voice media streams. It previously used in-memory state (`stream_registry`) which limited it to a single worker.

## Scaling Solution: Stateless Calls + Redis State

We chose **Option 1: Stateless Calls with Redis State** to enable horizontal scaling.

### How It Works

```
                        ┌──────────────┐
                        │    nginx     │
                        │  (upstream)  │
                        └──────┬───────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
             ┌───────────┐ ┌───────────┐ ┌───────────┐
             │ calls-1   │ │ calls-2   │ │ calls-3   │
             │ (replica) │ │ (replica) │ │ (replica) │
             └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
                   │              │              │
                   └──────────────┼──────────────┘
                                  ▼
                          ┌──────────────┐
                          │    Redis     │
                          │  call state  │
                          │  counters    │
                          └──────────────┘
```

### Key Components

#### `server/calls_state.py` — CallStateManager

- **Active calls counter**: Atomic Redis counter (`calls:active_count`)
- **Call session state**: JSON in Redis with TTL, keyed by `call_sid`
- **Max concurrent enforcement**: Atomic check-and-increment via Redis WATCH/MULTI
- **Graceful rejection**: Returns 503 when max concurrent reached

#### Redis Key Space

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `calls:active_count` | — | Global active call counter |
| `calls:state:{call_sid}` | 3600s | Per-call session state |
| `calls:lock:{call_sid}` | 60s | Optional per-call lock |

### MAX_CONCURRENT_CALLS Enforcement

- **Default**: 50 calls (configurable via env var)
- **Zero or negative** values are rejected — defaults to 50 (no "unlimited" mode)
- **Atomic**: Uses Redis WATCH/MULTI to prevent race conditions
- **Graceful**: Returns a rejection response, not a crash

### Scaling

```bash
# Scale calls service to 3 replicas
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale prosaas-calls=3
```

Since state lives in Redis, any replica can handle any call. No sticky routing needed.

### Graceful Degradation

When `MAX_CONCURRENT_CALLS` is reached:
1. New incoming calls receive a graceful rejection
2. The `calls_rejected_max_concurrent` metric counter increments
3. Twilio can be configured to play a fallback message or redirect to WhatsApp

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_CONCURRENT_CALLS` | `50` | Maximum concurrent active calls |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection for state storage |

### Monitoring

- Active calls: `redis-cli GET calls:active_count`
- Call state: `redis-cli GET calls:state:{call_sid}`
- Metrics endpoint: `GET /metrics.json` → `calls_active`, `calls_started`, `calls_rejected_max_concurrent`

### Key Files

| File | Purpose |
|------|---------|
| `server/calls_state.py` | Redis-backed state manager |
| `server/metrics.py` | Call metrics counters |
| `docker-compose.prod.yml` | Calls service configuration |
| `server/calls_scaling.md` | This document |
