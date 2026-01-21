# Production Clean Run Guide

## Overview

This guide ensures production runs cleanly with:
1. ✅ No extra backend/legacy services
2. ✅ No DNS errors (proper handling with exponential backoff)
3. ✅ No fake ERROR logs
4. ✅ Minimal log spam (quiet by default, verbose only with LOG_LEVEL=DEBUG)

## Services in Production

**Required Services:**
- `prosaas-api` - Main API server (port 5000)
- `prosaas-calls` - WebSocket/Call handling (port 5050)
- `worker` - Background job processing (RQ)
- `redis` - Queue and cache
- `nginx` - Reverse proxy (ports 80, 443)
- `frontend` - Static files

**Optional Services:**
- `baileys` - WhatsApp integration (if enabled)
- `n8n` - Automation platform (if enabled)

**NOT in Production:**
- ❌ `backend` - Disabled with `profiles: ["legacy"]`
- ❌ `db` - Use external managed database (Neon, Supabase, etc.)

## Deployment

### 1. Deploy Production Services

```bash
# Use the production deployment script
./scripts/dcprod.sh up -d --build

# Or manually with both compose files
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 2. Validate Deployment

```bash
# Run validation script
./scripts/validate_production.sh
```

This checks:
- ✅ No backend service running
- ✅ All required services are running
- ✅ DNS configuration is correct
- ✅ LOG_LEVEL=INFO is set
- ✅ No DNS errors in logs
- ✅ Log verbosity is reasonable
- ✅ No fake ERROR messages

### 3. Check Service Status

```bash
# View running services (should not show backend)
./scripts/dcprod.sh ps

# View logs (should be clean and minimal)
docker logs prosaas-api --tail 50
docker logs prosaas-calls --tail 50
docker logs prosaas-worker --tail 50
```

## DNS Error Handling

### Configuration

All production services use external DNS to prevent transient failures:

```yaml
dns:
  - 1.1.1.1  # Cloudflare
  - 8.8.8.8  # Google
dns_search: ["."]
dns_opt:
  - ndots:0
  - timeout:2
  - attempts:2
```

### Error Recovery

The reminder scheduler implements graduated backoff for DNS errors:
- **First attempt**: Immediate
- **Second attempt**: 30s backoff
- **Third attempt**: 60s backoff
- **Final attempt**: 120s backoff

Errors are rate-limited to prevent log spam:
- Only logs every 5th failure
- First failure: WARNING level
- Subsequent: DEBUG level

## Log Levels

### Production (Default)

```bash
LOG_LEVEL=INFO  # Set in docker-compose.prod.yml
```

- ✅ Important milestones logged
- ✅ Warnings and errors logged
- ❌ No verbose frame/latency logs
- ❌ No "SAFETY Transcription successful" spam
- ❌ No websocket.close double-close errors

### Debug Mode

```bash
LOG_LEVEL=DEBUG  # Set in .env or docker-compose override
```

- ✅ All verbose logging enabled
- ✅ Frame-by-frame audio processing
- ✅ Latency breakdowns
- ✅ WebSocket state transitions

## Verification Checklist

Run `./scripts/validate_production.sh` to check:

- [ ] No `backend` service in `docker compose ps`
- [ ] `prosaas-api` is running and healthy
- [ ] `prosaas-calls` is running and healthy
- [ ] `worker` is running and healthy
- [ ] `redis` is running and healthy
- [ ] `nginx` is running and healthy
- [ ] DNS configuration present in worker
- [ ] LOG_LEVEL=INFO in production compose
- [ ] No DNS errors in recent logs
- [ ] Log verbosity is reasonable (< 50 DEBUG messages per 100 lines)
- [ ] No fake ERROR messages in logs

## Troubleshooting

### Backend Service Running

If `backend` appears in production:

```bash
# Stop the service
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml rm -f backend

# Verify it's gone
./scripts/dcprod.sh ps
```

### DNS Errors Persist

1. Check DNS configuration in compose files
2. Verify network connectivity: `docker exec prosaas-worker ping -c 3 1.1.1.1`
3. Check logs for rate-limited messages: `docker logs prosaas-worker | grep DNS`

### Excessive Logs

1. Verify LOG_LEVEL: `docker exec prosaas-worker env | grep LOG_LEVEL`
2. Should show: `LOG_LEVEL=INFO`
3. If not, update docker-compose.prod.yml and redeploy

### Fake ERROR Messages

If you see:
- "SAFETY Transcription successful" as ERROR → Fixed in media_ws_ai.py (now DEBUG)
- "websocket.close already closed" as ERROR → Fixed in media_ws_ai.py (now DEBUG)

If still appearing, ensure you've rebuilt the image:
```bash
./scripts/dcprod.sh up -d --build --force-recreate
```

## Monitoring

### Quick Health Check

```bash
# Check all services are healthy
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Health}}"

# Check logs for errors (should be minimal)
docker logs prosaas-worker --since 10m | grep -i error | wc -l
```

### Expected Log Volume

In production (LOG_LEVEL=INFO):
- **Normal call**: ~20-30 log lines total
- **Worker cycle**: 1-2 lines per hour (only if work processed)
- **WhatsApp check**: 1 line per hour (only if sessions found)
- **Reminder check**: 1 line per hour (only if reminders sent)

### Key Metrics

- ✅ No "backend" in `docker compose ps`
- ✅ < 5 ERROR messages per hour (excluding real errors)
- ✅ < 10 DNS warnings per day
- ✅ < 100 DEBUG messages per 1000 log lines

## Related Files

- `docker-compose.prod.yml` - Production service overrides
- `scripts/dcprod.sh` - Production deployment wrapper
- `scripts/validate_production.sh` - Validation script
- `server/services/notifications/reminder_scheduler.py` - DNS error handling
- `server/media_ws_ai.py` - WebSocket and logging fixes
- `server/services/whatsapp_session_service.py` - Rate-limited checks
