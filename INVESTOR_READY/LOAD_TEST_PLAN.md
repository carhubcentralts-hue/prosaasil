# ProSaaS Load Test Plan

## Overview

This document outlines the load testing strategy for ProSaaS to validate scaling under production conditions.

## Test Targets

| Service | Endpoint | Method | Expected RPS |
|---------|----------|--------|-------------|
| API | `GET /api/health` | HTTP | 1000+ |
| API | `POST /api/leads` | HTTP | 100+ |
| API | `POST /api/whatsapp/send` | HTTP | 50+ |
| Calls | WebSocket `/ws/twilio-media` | WS | 50 concurrent |
| Worker | Queue throughput | Redis | 100 jobs/min |

## Tools

- **k6** (recommended) — scriptable load testing
- **wrk** — simple HTTP benchmarking
- **locust** — Python-based (if preferred)

## Test Scripts

### 1. API Health Check (Baseline)

```bash
# Using wrk (install: apt install wrk)
wrk -t4 -c100 -d30s http://localhost:5000/api/health
```

### 2. API Endpoint Load Test (k6)

```javascript
// save as loadtest_api.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 },  // Ramp up
    { duration: '1m', target: 50 },   // Sustained load
    { duration: '10s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95th percentile < 500ms
    http_req_failed: ['rate<0.01'],    // Error rate < 1%
  },
};

export default function () {
  const res = http.get('http://localhost:5000/api/health');
  check(res, {
    'status 200': (r) => r.status === 200,
    'response time < 200ms': (r) => r.timings.duration < 200,
  });
  sleep(0.1);
}
```

Run: `k6 run loadtest_api.js`

### 3. WhatsApp Queue Throughput

```python
#!/usr/bin/env python3
"""Test queue throughput by enqueuing mock jobs."""
import time
import redis
from rq import Queue

r = redis.from_url("redis://localhost:6379/0")

def dummy_job(x):
    return x * 2

q = Queue("high", connection=r)
start = time.time()
count = 100

for i in range(count):
    q.enqueue(dummy_job, i)

elapsed = time.time() - start
print(f"Enqueued {count} jobs in {elapsed:.2f}s ({count/elapsed:.0f} jobs/sec)")
```

### 4. Concurrent Calls Test

```python
#!/usr/bin/env python3
"""Test MAX_CONCURRENT_CALLS enforcement."""
import redis
import json

r = redis.from_url("redis://localhost:6379/0")

# Reset counter
r.set("calls:active_count", 0)

# Simulate reaching max
max_calls = int(r.get("calls:active_count") or 0)
print(f"Current active: {max_calls}")

# Increment to max
for i in range(50):
    r.incr("calls:active_count")

current = int(r.get("calls:active_count"))
print(f"After 50 increments: {current}")
print(f"Should reject next call: {current >= 50}")

# Cleanup
r.set("calls:active_count", 0)
print("Reset to 0")
```

## Success Criteria

| Metric | Target |
|--------|--------|
| API p95 latency | < 500ms |
| API error rate | < 1% |
| Concurrent calls limit | Enforced (no overflow) |
| Worker throughput | > 50 jobs/min |
| WhatsApp message delivery | > 95% success |
| System uptime under load | > 99.9% |

## Schedule

- **Pre-launch**: Full load test suite
- **Monthly**: Baseline health check load test
- **Before scaling changes**: Comparative load test
