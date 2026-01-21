# State Management & Scaling Constraints

## CRITICAL: In-Memory State Limitations

### Current State (Per-Process)

The following are stored **IN-MEMORY** (not Redis):

1. **stream_registry** (`server/stream_state.py`)
   - Active call sessions
   - Media timestamps
   - Performance stamps
   - Call metadata

### Scaling Constraint

**⚠️ SINGLE WORKER ONLY**

The `prosaas-calls` service **MUST** run with a single worker:

```yaml
# docker-compose.prod.yml
prosaas-calls:
  command: ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "5050", 
            "--ws", "websockets", "--workers", "1"]  # MUST BE 1
```

### Why Single Worker?

- `stream_registry` is in-memory Python dict
- Each worker has its own registry
- If call connects to worker A, metadata is in A's memory
- If next request routes to worker B, B doesn't have the state
- Result: Lost call context, crashes, dropped calls

### What Happens If You Add Workers?

**DON'T!** Unless you refactor to Redis:

```python
# Future refactor needed (NOT DONE YET):
# Replace stream_registry with Redis
import redis
redis_client = redis.from_url(REDIS_URL)

def mark_start(call_sid):
    redis_client.hset(f"call:{call_sid}", "started", "true")
    redis_client.hset(f"call:{call_sid}", "last_media_at", time.time())
```

### Safe to Scale

These services CAN scale horizontally (no in-memory state):

- ✅ `prosaas-api` - stateless REST
- ✅ `prosaas-worker` - Redis queue based
- ✅ `baileys` - WhatsApp session in volume
- ❌ `prosaas-calls` - **IN-MEMORY STATE - SINGLE WORKER ONLY**

## Future Work: Redis State Migration

To enable multi-worker for `prosaas-calls`:

1. Replace `StreamRegistry` with Redis-based implementation
2. Move all call state to Redis with TTL
3. Use Redis pub/sub for call cancellation
4. Then scale workers: `--workers 4`

**Until then**: Keep `--workers 1` or calls WILL break!
