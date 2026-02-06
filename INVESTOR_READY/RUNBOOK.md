# ProSaaS Runbook

## Overview

This runbook covers operational procedures for ProSaaS production deployment.

## Service Architecture

| Service | Port | Health Check | Purpose |
|---------|------|-------------|---------|
| nginx | 80/443 | `GET /health` | Reverse proxy, SSL termination |
| prosaas-api | 5000 | `GET /api/health` | REST API, business logic |
| prosaas-calls | 5050 | `GET /health` | WebSocket, Twilio voice calls |
| worker | — | Redis ping | Background job processing |
| scheduler | — | Redis ping | Periodic job scheduling |
| baileys | 3300 | `GET /health` | WhatsApp (Baileys) gateway |
| redis | 6379 | `redis-cli ping` | Queue + cache + call state |
| frontend | 80 | `GET /health` | Static SPA (React) |

## Starting the System

```bash
# 1. Ensure Docker network exists
./scripts/ensure_docker_network.sh

# 2. Development
docker compose up -d

# 3. Production (single worker)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. Production (multi-worker)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile multi-worker up -d

# 5. Production (multi-shard WhatsApp)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile multi-shard up -d
```

## Common Failure Scenarios

### 1. API Service Down

**Symptoms**: 502 errors from nginx, frontend shows connection errors.

**Steps**:
1. Check logs: `docker compose logs prosaas-api --tail=100`
2. Check health: `curl http://localhost:5000/api/health`
3. Check DB connectivity: `curl http://localhost:5000/readyz`
4. Restart: `docker compose restart prosaas-api`

### 2. Calls Service Unresponsive

**Symptoms**: Incoming calls fail, WebSocket connections drop.

**Steps**:
1. Check logs: `docker compose logs prosaas-calls --tail=100`
2. Check health: `curl http://localhost:5050/health`
3. Check active calls via Redis: `docker compose exec redis redis-cli GET calls:active_count`
4. If stuck calls: `docker compose exec redis redis-cli SET calls:active_count 0`
5. Restart: `docker compose restart prosaas-calls`

### 3. Worker Not Processing Jobs

**Symptoms**: Emails not syncing, broadcasts stuck, thumbnails not generating.

**Steps**:
1. Check logs: `docker compose logs worker --tail=100`
2. Check Redis connectivity: `docker compose exec redis redis-cli ping`
3. Check queue lengths: `docker compose exec redis redis-cli LLEN rq:queue:default`
4. Check failed queue: `docker compose exec redis redis-cli LLEN rq:queue:failed`
5. Restart: `docker compose restart worker`

### 4. WhatsApp (Baileys) Disconnected

**Symptoms**: WhatsApp messages not sending/receiving.

**Steps**:
1. Check logs: `docker compose logs baileys --tail=100`
2. Check health: `curl http://localhost:3300/health` (from within docker network)
3. Check WhatsApp health via API: `curl http://localhost:5000/health/whatsapp`
4. Re-scan QR: Access business settings → WhatsApp → Re-connect
5. Restart: `docker compose restart baileys`

### 5. Redis Down

**Symptoms**: All background jobs stop, calls state lost, worker unresponsive.

**Steps**:
1. Check status: `docker compose logs redis --tail=50`
2. Restart: `docker compose restart redis`
3. After restart: workers and calls service will auto-reconnect

### 6. Database Migration Failed

**Symptoms**: `migrate` service shows error status, API returns schema errors.

**Steps**:
1. Check migration logs: `docker compose logs migrate`
2. Fix migration issue in code
3. Re-run: `docker compose restart migrate`
4. After migration: restart dependent services

## Scaling Operations

### Scale Workers

```bash
# Scale default worker to 3 replicas
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale worker=3

# Or use multi-worker profile for queue-dedicated workers
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile multi-worker up -d
```

### Scale Baileys (WhatsApp)

```bash
# Activate multi-shard profile
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile multi-shard up -d
```

Then assign businesses to shards via DB: `UPDATE business SET whatsapp_shard = 2 WHERE id = ?`

### Adjust Call Concurrency

Set env var `MAX_CONCURRENT_CALLS` (default: 50) and restart calls service.

## Monitoring

- Health: `curl http://localhost:5000/api/health`
- Readiness: `curl http://localhost:5000/readyz`
- Metrics: `curl http://localhost:5000/metrics.json?token=$INTERNAL_SECRET`
- WhatsApp: `curl http://localhost:5000/health/whatsapp`
- Version: `curl http://localhost:5000/version`
