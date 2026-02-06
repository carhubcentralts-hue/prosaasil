# Production Readiness — Proof of Wiring

## SSOT Configuration Layer

All operational configuration is centralized in `server/config/__init__.py`:

| Setting | Default | Env Override |
|---------|---------|-------------|
| BAILEYS_SHARDS | 1 | `BAILEYS_NUM_SHARDS` |
| BAILEYS_PORT | 3300 | `BAILEYS_PORT` |
| MAX_CONCURRENT_CALLS | 50 | `MAX_CONCURRENT_CALLS` |
| METRICS_ENABLED | true | `METRICS_ENABLED` |
| METRICS_TOKEN | *(none)* | `METRICS_TOKEN` |
| REDIS_URL | redis://redis:6379/0 | `REDIS_URL` |

**Rule**: No `os.getenv()` scattered in business logic. All reads go through `server.config`.

## Proof of Wiring

### 1. Baileys Shard Routing
- **SSOT**: `server/whatsapp_shard_router.py` → `get_baileys_base_url(business_id)`
- **Wired in**: `routes_whatsapp.py`, `whatsapp_provider.py`, `broadcast_worker.py`
- **No direct** `BAILEYS_BASE_URL` usage outside config/router
- **Migration 139**: `ALTER TABLE business ADD COLUMN whatsapp_shard INTEGER NOT NULL DEFAULT 1`
- **Test**: `tests/test_ssot_wiring.py::test_shard_routing_*` (5 tests)

### 2. Metrics
- **SSOT**: `server/metrics.py` → `register_metrics_endpoint(app)`
- **Wired in**: `server/app_factory.py` (conditional on METRICS_ENABLED + METRICS_TOKEN)
- **Test**: `tests/test_ssot_wiring.py::test_metrics_endpoint_*` (2 tests)

### 3. Calls Concurrency
- **SSOT**: `server/calls_state.py` + `server/services/calls_capacity.py`
- **Wired in**: `server/routes_twilio.py` (try_acquire_call_slot on incoming calls)
- **Config**: `MAX_CONCURRENT_CALLS` from `server.config` (default 50, never 0 in prod)
- **Test**: `tests/test_ssot_wiring.py::test_calls_state_manager_init`

### 4. Queue SSOT
- **SSOT**: `server/queues.py` — queue names, worker groups, job defaults, dead-letter
- **Worker groups**: `worker-high`, `worker-default`, `worker-low`, `worker-media`
- **Compose**: `docker-compose.prod.yml` uses matching queue assignments

### 5. CI Quality Gate
- **SSOT**: `scripts/quality_gate.sh` runs all checks
- **SSOT check**: `scripts/no_duplicate_ssot_checks.sh` validates no duplicate wiring
- CI uses `requirements.lock` for pip-audit

## Tests That Pass

| Test File | Tests | What It Validates |
|-----------|-------|-------------------|
| `test_ssot_wiring.py` | 10 | Config defaults, shard routing, metrics auth, calls state |
| `test_appointment_reminder_weekday_fix.py` | 3 | Hebrew date formatting |
| `test_business_settings_cache.py` | 8 | Cache TTL, eviction, isolation |
| `test_cors_recording_playback.py` | 3 | CORS headers |
| `test_export_leads_by_status.py` | 4 | CSV export |
| `test_hebrew_datetime_year_correction.py` | 4 | Year correction |
| `test_scheduled_messages_first_name.py` | 7 | Variable substitution |
| `test_webhook_payload.py` | 2 | Webhook serialization |

## Grep Gates (all pass)

```
✅ No direct BAILEYS_BASE_URL usage outside config/router
✅ register_metrics_endpoint called in app_factory
✅ calls_capacity used in routes_twilio
✅ whatsapp_shard migration exists in db_migrate.py
```

## Docker Compose Profiles

| Profile | Services | Usage |
|---------|----------|-------|
| *(default)* | API, calls, worker, baileys, redis, nginx, frontend | Standard production |
| `multi-worker` | worker-high, worker-default, worker-low | Scaled workers |
| `multi-shard` | baileys-2 | Additional WhatsApp shard |

```bash
# Standard production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# With multi-worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile multi-worker up -d

# With multi-shard
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile multi-shard up -d

# Full production
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile multi-worker --profile multi-shard up -d
```

## Safety Fallback

If `business.whatsapp_shard` column is missing (migration not yet run):
- `/api/me/context` returns a fallback response instead of 500
- Shard router falls back to hash-based routing (no DB column needed)
- Log warning: "DB schema behind — please run db_migrate"
