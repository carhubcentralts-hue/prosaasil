# Worker Commands Guide - Service Name vs Container Name

## Understanding the Difference

In Docker Compose, there are TWO ways to reference a container:

1. **Service Name** (defined in `docker-compose.yml`) = `worker`
2. **Container Name** (the actual container) = `prosaas-worker`

## Correct Commands

### Using Docker Compose (Service Name = `worker`)

```bash
# View logs
docker compose logs worker
docker compose logs -f worker          # Follow logs
docker compose logs --tail=50 worker   # Last 50 lines

# Check status
docker compose ps worker

# Execute command inside container
docker compose exec worker python -c "import redis; print('OK')"

# Restart service
docker compose restart worker

# Stop/Start
docker compose stop worker
docker compose start worker
```

### Using Docker CLI (Container Name = `prosaas-worker`)

```bash
# View logs
docker logs prosaas-worker
docker logs -f prosaas-worker          # Follow logs
docker logs --tail=50 prosaas-worker   # Last 50 lines

# Check status
docker ps --filter name=prosaas-worker

# Execute command inside container
docker exec prosaas-worker python -c "import redis; print('OK')"

# Inspect health
docker inspect prosaas-worker --format='{{.State.Health.Status}}'

# Restart container
docker restart prosaas-worker

# Stop/Start
docker stop prosaas-worker
docker start prosaas-worker
```

## ❌ Common Mistakes

```bash
# ❌ WRONG - Using container name with docker compose
docker compose logs prosaas-worker     # ERROR: no such service

# ❌ WRONG - Using service name with docker commands
docker logs worker                     # ERROR: no such container
```

## Checking Worker Status

### 1. Is the worker running?

```bash
# Method 1: Using docker compose
docker compose ps worker

# Method 2: Using docker CLI
docker ps --filter name=prosaas-worker
```

### 2. Is the worker healthy?

```bash
# Check health status
docker inspect prosaas-worker --format='{{.State.Health.Status}}'

# Expected output: "healthy" or "starting"
# If "unhealthy" or no healthcheck - see troubleshooting below
```

### 3. Did the worker start successfully?

```bash
# Look for WORKER_START message
docker compose logs worker | grep "WORKER_START"

# OR
docker logs prosaas-worker | grep "WORKER_START"
```

### 4. Is the worker registered in Redis?

```bash
# Check Redis worker registry
docker exec prosaas-redis redis-cli SMEMBERS rq:workers

# Expected output: Something like "rq:worker:prosaas-worker-12345"
# If empty → Worker didn't register (check logs)
```

### 5. Which queues is the worker listening to?

```bash
# Check worker queue configuration
docker compose exec worker python -c "
from rq import Worker
import redis
conn = redis.from_url('redis://redis:6379/0')
workers = Worker.all(connection=conn)
for w in workers:
    queues = [q.name for q in w.queues]
    print(f'Worker {w.name}: {queues}')
"

# Expected output: Should include 'default' queue
```

## Troubleshooting

### Problem: Worker is "unhealthy"

```bash
# 1. Check health check logs
docker inspect prosaas-worker --format='{{json .State.Health}}' | jq

# 2. Test Redis connection manually
docker compose exec worker python -c "
import redis
r = redis.from_url('redis://redis:6379/0')
r.ping()
print('Redis OK')
"

# 3. If healthcheck keeps failing, check docker-compose.yml healthcheck config
#    - Make sure start_period is at least 30s
#    - Make sure Redis is accessible at redis://redis:6379/0
```

### Problem: Worker not processing jobs

```bash
# 1. Check if worker is listening to the right queue
docker compose exec worker python -c "
from rq import Worker
import redis
conn = redis.from_url('redis://redis:6379/0')
workers = Worker.all(connection=conn)
print(f'Total workers: {len(workers)}')
for w in workers:
    queues = [q.name for q in w.queues]
    print(f'{w.name}: {queues}')
    if 'default' in queues:
        print('✓ Worker listening to default queue')
"

# 2. Check if jobs are in the queue
docker exec prosaas-redis redis-cli LLEN rq:queue:default

# 3. Check worker logs for errors
docker compose logs --tail=100 worker | grep -i error
```

### Problem: "no such service: prosaas-worker"

**This means you're using the wrong name with docker compose!**

```bash
# ❌ Wrong
docker compose logs prosaas-worker

# ✓ Correct
docker compose logs worker

# OR use docker CLI directly
docker logs prosaas-worker
```

## Quick Reference Card

| Task | Docker Compose (service) | Docker CLI (container) |
|------|-------------------------|----------------------|
| View logs | `docker compose logs worker` | `docker logs prosaas-worker` |
| Follow logs | `docker compose logs -f worker` | `docker logs -f prosaas-worker` |
| Check status | `docker compose ps worker` | `docker ps --filter name=prosaas-worker` |
| Execute command | `docker compose exec worker <cmd>` | `docker exec prosaas-worker <cmd>` |
| Restart | `docker compose restart worker` | `docker restart prosaas-worker` |
| Check health | N/A | `docker inspect prosaas-worker --format='{{.State.Health.Status}}'` |

## Production Deployment

When deploying to production:

```bash
# 1. Deploy with both compose files
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 2. Wait for services to start
sleep 10

# 3. Check worker is running
docker compose ps worker

# 4. Check worker logs
docker compose logs worker | tail -50

# 5. Verify worker registered in Redis
docker exec prosaas-redis redis-cli SMEMBERS rq:workers

# 6. Test job processing
# (Trigger a sync and watch logs)
docker compose logs -f worker | grep "🔔"
```

## Environment Variables

The worker needs these environment variables:

```env
REDIS_URL=redis://redis:6379/0
RQ_QUEUES=high,default,low
SERVICE_ROLE=worker
```

Check they're set correctly:

```bash
docker compose exec worker printenv | grep -E "REDIS_URL|RQ_QUEUES|SERVICE_ROLE"
```
