# 🔥 Production Logging Deployment Guide

**Goal**: Minimal, clean logs in production (90-95% reduction from development)

This guide describes the logging configuration for ProSaaS in production environments.

---

## 📋 Quick Summary

### Production Settings (Minimal Logs)
```bash
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
```

### Development Settings (Full Logs)
```bash
LOG_LEVEL=DEBUG
PYTHONUNBUFFERED=1
```

---

## 🎯 Environment Variables

### `LOG_LEVEL` (Required for Production)

Controls the logging verbosity across the entire application.

**Production (Recommended)**:
```bash
LOG_LEVEL=INFO
```
- ✅ Only essential logs: call start/end, errors, warnings
- ✅ No frame-by-frame audio logs
- ✅ No TX_RESPONSE start/end spam
- ✅ No "Found 0 stale sessions" spam
- ✅ External libraries (uvicorn, sqlalchemy, httpx) silenced to WARNING

**Development**:
```bash
LOG_LEVEL=DEBUG
```
- Full verbose logging
- Frame-by-frame audio debugging
- All internal module logs visible

**Other Levels**:
- `WARNING` - Only warnings and errors (ultra-quiet)
- `ERROR` - Only errors (troubleshooting mode)

### `PYTHONUNBUFFERED` (Required)

Ensures logs are written immediately (no buffering).

```bash
PYTHONUNBUFFERED=1
```

This is critical for:
- Real-time log streaming
- Docker container logs
- Production monitoring

### `LOG_JSON` (Optional)

Enable JSON-formatted logs for log aggregation systems (Datadog, CloudWatch, etc.).

```bash
LOG_JSON=1  # JSON format
LOG_JSON=0  # Human-readable format (default)
```

**JSON Format Example**:
```json
{"timestamp":"2024-01-21T19:30:26","level":"INFO","module":"media_ws_ai","message":"Call started: call_sid=CA123..."}
```

**Human-Readable Format Example**:
```
[2024-01-21 19:30:26] INFO     [media_ws_ai] Call started: call_sid=CA123...
```

---

## 🚀 Deployment Configurations

### Docker Compose Production

**File**: `docker-compose.prod.yml`

All production services are pre-configured with `LOG_LEVEL=INFO`:

```yaml
services:
  prosaas-api:
    environment:
      LOG_LEVEL: INFO
      PYTHONUNBUFFERED: 1
  
  prosaas-calls:
    environment:
      LOG_LEVEL: INFO
      PYTHONUNBUFFERED: 1
    command: ["uvicorn", "asgi:app", ..., "--log-level", "info"]
  
  worker:
    environment:
      LOG_LEVEL: INFO
      PYTHONUNBUFFERED: 1
  
  baileys:
    environment:
      LOG_LEVEL: INFO  # For Node.js service (future)
```

### Railway / Replit / Cloud Deployment

Add these environment variables to your deployment:

```bash
# Logging
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
LOG_JSON=0

# Optional: Enable JSON for log aggregation
LOG_JSON=1
```

### Uvicorn (Calls Service)

The calls service uses uvicorn with production-safe settings:

```bash
uvicorn asgi:app \
  --host 0.0.0.0 \
  --port 5050 \
  --log-level info \
  --ws websockets \
  --timeout-keep-alive 75
```

**Important**: Do NOT use `--access-log` in production (generates massive spam).

---

## 📊 Expected Log Volume

### Before Logging Cleanup

**One call generates**:
- 500-2000+ log lines
- Frame-by-frame audio logs (every 20ms)
- TX_RESPONSE start/end for every response
- WhatsApp "Found 0 stale sessions" every 5 minutes
- Worker "idle" messages

**Example spam**:
```
[TX_RESPONSE] start response_id=resp_12345...
[AUDIO_DELTA] response_id=resp_12345, bytes=320
[AUDIO_DELTA] response_id=resp_12345, bytes=320
[AUDIO_DELTA] response_id=resp_12345, bytes=320
... (repeated 100+ times)
[TX_RESPONSE] end response_id=resp_12345, frames=150
[WHATSAPP_SESSION] Check #45: Found 0 stale sessions
```

### After Logging Cleanup (Production)

**One call generates**:
- **10-30 log lines** (95% reduction!)
- Only macro events logged
- No frame-by-frame spam
- No "Found 0" spam

**Example production logs**:
```
[INFO] 🚀 [CALL_START] call_sid=CA123, business_id=456, direction=inbound
[INFO] ✅ [DB] Customer context loaded: name=David, phone=+972...
[INFO] 🔌 [REALTIME] OpenAI connected in 234ms
[INFO] 🎤 [GREETING] Playing greeting audio
[INFO] 💬 [TRANSCRIPT] Customer: "שלום, אני רוצה לתאם פגישה"
[INFO] 🤖 [RESPONSE_CREATED] response_id=resp_123, type=appointment
[INFO] 📅 [TOOL_CALL] check_availability: 2024-01-25 14:00
[INFO] ✅ [TOOL_RESULT] Available slots: 3
[INFO] 💬 [TRANSCRIPT] AI: "יש לי זמינות ב..."
[INFO] 🔚 [CALL_END] duration=45s, reason=customer_hangup
```

---

## 🔍 What Gets Logged in Production (LOG_LEVEL=INFO)

### ✅ Always Logged (INFO Level)

**Calls/Realtime**:
- Call start: `call_sid`, `business_id`, `direction`, `mode`
- DB context loading
- OpenAI connection status and latency
- Customer transcript (turn-level, not word-by-word)
- AI response created/done (summary, no details)
- Tool calls and results (appointments, etc.)
- Barge-in events (once per occurrence)
- Call end: duration, reason, metrics summary
- Errors and exceptions (with full stacktrace)

**WhatsApp**:
- Connection status changes
- Message received (jid/tenant only, not content)
- Stale sessions found (only if count > 0)
- Errors and retries

**Worker**:
- Worker started (queues, PID)
- Job enqueued
- Job completed (with duration)
- Job failed (with stacktrace)

### ❌ NOT Logged in Production (DEBUG Level)

**Suppressed in LOG_LEVEL=INFO**:
- Frame-by-frame audio logs (`[AUDIO_DELTA]`)
- TX_RESPONSE start/end for each response
- Watchdog checks (except final timeout)
- "Found 0 stale sessions" checks
- Per-frame RMS/volume calculations
- Payload previews and instruction lengths
- Step-by-step job processing
- Queue size checks
- Health check pings (uvicorn access logs)

---

## 🔧 Troubleshooting

### Enable DEBUG Logging Temporarily

If you need to debug an issue in production:

1. **Set environment variable**:
   ```bash
   LOG_LEVEL=DEBUG
   ```

2. **Restart the service**:
   ```bash
   docker compose restart prosaas-calls
   ```

3. **Collect logs**:
   ```bash
   docker compose logs -f prosaas-calls > debug.log
   ```

4. **After debugging, restore production settings**:
   ```bash
   LOG_LEVEL=INFO
   docker compose restart prosaas-calls
   ```

### Verify Logging Configuration

Check that logging is configured correctly:

```bash
# View startup logs
docker compose logs prosaas-api | grep LOGGING

# Should see:
# [INFO] LOGGING CONFIGURED: level=INFO, json=0
```

### Check Log Volume

Monitor log volume to ensure it's minimal:

```bash
# Count log lines per minute
docker compose logs --tail=100 prosaas-calls | wc -l

# Production should be < 50 lines/minute during active calls
# Development could be 500-1000+ lines/minute
```

---

## 🎓 Best Practices

### 1. Use LOG_LEVEL=INFO in Production
- Always set `LOG_LEVEL=INFO` for production deployments
- Only use `DEBUG` for troubleshooting

### 2. Monitor Log Volume
- Set up alerts if log volume exceeds thresholds
- Production calls should generate 10-30 lines max

### 3. Enable JSON for Log Aggregation
- Use `LOG_JSON=1` if sending logs to Datadog/CloudWatch
- Keep `LOG_JSON=0` for human-readable Docker logs

### 4. Rate Limiting
- All repeating logs use rate limiting automatically
- Example: Watchdog logs every 3 seconds max, not every iteration

### 5. Error Handling
- Errors always logged with full stacktrace (even in production)
- Warnings logged for exceptional cases
- INFO for normal operations

---

## 📝 Summary

### Production ENV Variables (Copy-Paste Ready)

```bash
# ========================================
# PRODUCTION LOGGING CONFIGURATION
# ========================================
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
LOG_JSON=0

# Optional: Enable for log aggregation
# LOG_JSON=1
```

### Development ENV Variables

```bash
# ========================================
# DEVELOPMENT LOGGING CONFIGURATION
# ========================================
LOG_LEVEL=DEBUG
PYTHONUNBUFFERED=1
LOG_JSON=0
```

---

## 🚀 Deployment Checklist

Before deploying to production:

- [ ] Set `LOG_LEVEL=INFO` in environment
- [ ] Set `PYTHONUNBUFFERED=1` in environment
- [ ] Update `docker-compose.prod.yml` with logging settings
- [ ] Test that log volume is minimal (10-30 lines per call)
- [ ] Verify no "Found 0" spam in logs
- [ ] Verify no frame-by-frame audio spam
- [ ] Confirm errors still logged with full stacktrace

---

## 📞 Support

For questions about logging configuration:
1. Check `server/logging_config.py` for implementation details
2. Review `server/utils/log_rate_limit.py` for rate limiting utilities
3. See examples in `LOGGING_CONVERSION_SUMMARY.md`

---

**Last Updated**: 2024-01-21  
**Version**: 1.0  
**Status**: ✅ Production Ready
