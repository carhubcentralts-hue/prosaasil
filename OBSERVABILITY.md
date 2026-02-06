# ProSaaS Observability

## Overview

ProSaaS provides built-in observability without requiring external infrastructure (Prometheus, Grafana, etc. are optional add-ons).

## Health Endpoints

Every service exposes health endpoints for Docker healthchecks, load balancers, and monitoring.

### API Service (port 5000)

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `GET /api/health` | Full health: DB, migrations, schema | `{"status": "healthy"}` |
| `GET /healthz` | Liveness probe (always 200 if process alive) | `{"status": "ok"}` |
| `GET /readyz` | Readiness: DB + Baileys connectivity | `{"ready": true, ...}` |
| `GET /livez` | Kubernetes-compatible liveness | `ok` |
| `GET /version` | Build info | `{"build": 59, ...}` |
| `GET /warmup` | Cold start prevention (preloads AI/TTS) | `{"status": "warm"}` |
| `GET /health/whatsapp` | WhatsApp + AgentKit status | `{"baileys": {...}}` |
| `GET /health/agentkit` | AgentKit module status | `{"status": "ok"}` |

### Calls Service (port 5050)

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `GET /health` | Calls service health + active call count | `{"status": "healthy", "active_calls": N}` |

### Worker Service

- **Heartbeat**: Worker writes `worker:heartbeat` key to Redis every 30s
- **Monitor**: Check via `redis-cli GET worker:heartbeat`

### Baileys Service (port 3300)

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `GET /health` | Baileys health + session count | `{"status": "ok", "sessions": N}` |

## Metrics Endpoint

### `GET /metrics.json`

Returns JSON counters and gauges for operational monitoring.

**Authentication**: Requires `Authorization: Bearer $METRICS_TOKEN` header or `?token=` query param.

**Response format**:
```json
{
  "uptime_seconds": 3600.5,
  "counters": {
    "whatsapp_inbound_messages": 150,
    "whatsapp_outbound_messages": 200,
    "calls_started": 25,
    "calls_completed": 23,
    "calls_rejected_max_concurrent": 2,
    "queue_jobs_enqueued": 500,
    "queue_jobs_completed": 495,
    "queue_jobs_failed": 5
  },
  "gauges": {
    "calls_active": 3
  },
  "timestamp": 1706000000.0
}
```

### Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `whatsapp_inbound_messages` | Counter | Messages received via WhatsApp |
| `whatsapp_outbound_messages` | Counter | Messages sent via WhatsApp |
| `whatsapp_errors` | Counter | WhatsApp send/receive errors |
| `calls_started` | Counter | Total calls initiated |
| `calls_completed` | Counter | Calls completed successfully |
| `calls_rejected_max_concurrent` | Counter | Calls rejected (over limit) |
| `calls_errors` | Counter | Call processing errors |
| `calls_active` | Gauge | Currently active calls |
| `queue_jobs_enqueued` | Counter | Jobs added to queues |
| `queue_jobs_completed` | Counter | Jobs completed successfully |
| `queue_jobs_failed` | Counter | Jobs that failed |
| `queue_jobs_dead_letter` | Counter | Jobs moved to dead-letter queue |

## Docker Healthchecks

All services have Docker healthchecks configured in `docker-compose.yml`:

```yaml
# API
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s

# Worker (Redis connectivity check)
healthcheck:
  test: ["CMD-SHELL", "python -c \"import os,redis; r=redis.from_url(os.environ.get('REDIS_URL','redis://redis:6379/0')); r.ping()\""]
  interval: 30s

# Baileys
healthcheck:
  test: ["CMD-SHELL", "wget -qO- http://localhost:3300/health >/dev/null 2>&1 || exit 1"]
  interval: 15s
```

## Alerting (Optional)

For production alerting, integrate the `/metrics.json` endpoint with:
- **Uptime monitoring**: UptimeRobot, Better Uptime, or similar → `/api/health`
- **Prometheus**: Scrape `/metrics.json` with a JSON exporter
- **Custom**: Periodic curl + threshold checks via cron

## Log Levels

Control via `LOG_LEVEL` env var:
- `DEBUG` — Development (verbose)
- `INFO` — Production (recommended)
- `WARNING` — Minimal output
