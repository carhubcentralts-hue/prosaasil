# Docker Port Conflict Fix - Deployment Guide

## Problem Summary

The deployment was failing due to port conflicts on the Docker host:
- Redis port 6379 was exposed to the host
- Baileys port 3300 was exposed to the host
- Multiple stacks running simultaneously (prosaas-* and prosaasil-*)
- Docker-proxy conflicts causing containers to fail

In production, internal services should **NOT** expose ports to the host. They should only use `expose` to make them available within the Docker network. Only nginx (the reverse proxy) should publish ports 80/443 to the host.

## Changes Made

### 1. docker-compose.yml
**Redis Service:**
- Changed from `ports: - "6379:6379"` to `expose: - "6379"`
- Redis is now only accessible within the `prosaas-net` Docker network
- No external host port binding

**Baileys Service:**
- Changed from `ports: - "3300:3300"` to `expose: - "3300"`
- Baileys is now only accessible within the `prosaas-net` Docker network
- No external host port binding

### 2. docker-compose.prod.yml
- Already has correct override for Redis: `ports: []`
- No changes needed - production overrides are correct

### 3. Nginx Configuration
**Verified nginx uses correct service names:**
- ✅ `proxy_pass http://prosaas-api:5000` (not localhost)
- ✅ `proxy_pass http://prosaas-calls:5050` (not localhost)
- ✅ `proxy_pass http://frontend:80` (not localhost)
- ✅ `proxy_pass http://n8n:5678` (not localhost)

## Deployment Instructions

### Step 1: Stop and Remove All Previous Stacks (One-time cleanup)

```bash
# Stop all containers and remove orphans
docker compose down --remove-orphans

# Stop all running containers
docker stop $(docker ps -q) || true

# Remove all containers
docker rm $(docker ps -aq) || true

# Verify all containers are stopped
docker ps
# Should show empty list
```

### Step 2: Verify Network (Keep prosaas-net)

```bash
# Check that prosaas-net exists
docker network ls | grep prosaas-net

# If it doesn't exist, create it
docker network create prosaas-net
```

### Step 3: Deploy with Clean Build

```bash
# Build without cache to ensure fresh images
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache

# Start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Step 4: Verify Deployment

```bash
# Check all containers are running
docker ps

# Expected output should show:
# - nginx → Up + healthy
# - prosaas-api → Up + healthy
# - prosaas-calls → Up + healthy
# - frontend → Up + healthy
# - redis → Up
# - baileys → Up + healthy
# - worker → Up + healthy
# - n8n → Up
# - No Restart loops

# Check nginx can respond
curl -I http://localhost

# Expected: 200 / 301 / 302 (not timeout)

# Check logs for any errors
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50
```

## Architecture

### Port Exposure Summary

| Service | Internal Port | External Port | Access |
|---------|--------------|---------------|--------|
| nginx | 80, 443 | 80, 443 | Public (Host + Internet) |
| prosaas-api | 5000 | None | Internal (Docker network only) |
| prosaas-calls | 5050 | None | Internal (Docker network only) |
| frontend | 80 | None | Internal (Docker network only) |
| redis | 6379 | None | Internal (Docker network only) |
| baileys | 3300 | None | Internal (Docker network only) |
| n8n | 5678 | None | Internal (Docker network only) |
| worker | None | None | Internal (Docker network only) |

### Network Flow

```
Internet / Cloudflare
         ↓
    nginx:80/443 (Host port binding)
         ↓
    prosaas-net (Docker network)
         ↓
    ┌────────────────────────────────┐
    │                                │
    ├→ prosaas-api:5000             │
    ├→ prosaas-calls:5050           │
    ├→ frontend:80                  │
    ├→ n8n:5678                     │
    ├→ baileys:3300 ← prosaas-api  │
    ├→ redis:6379 ← all services    │
    └────────────────────────────────┘
```

## Benefits

1. **No Port Conflicts**: Multiple stacks can run on the same host without conflicts
2. **Security**: Internal services are not exposed to the host or internet
3. **Cleaner Architecture**: Clear separation between public (nginx) and internal services
4. **Docker Best Practices**: Follows Docker networking best practices
5. **Production Ready**: Configuration suitable for production deployments

## Troubleshooting

### Problem: Containers fail to start with "port already in use"
**Solution**: 
```bash
# Check what's using the port
sudo netstat -tulpn | grep :6379
sudo netstat -tulpn | grep :3300

# Stop the conflicting process or use the cleanup steps above
```

### Problem: Services can't communicate
**Solution**:
```bash
# Verify all services are on the same network
docker inspect prosaas-api | grep -A 10 Networks
docker inspect redis | grep -A 10 Networks

# They should all be on prosaas-net
```

### Problem: nginx shows "upstream not found"
**Solution**:
```bash
# Check nginx can resolve service names
docker exec -it <nginx-container-id> nslookup prosaas-api
docker exec -it <nginx-container-id> nslookup redis

# Verify services are running
docker ps | grep -E "(redis|prosaas-api|prosaas-calls|frontend)"
```

### Problem: 521 Error from Cloudflare
**Solution**:
```bash
# Check nginx is healthy
docker ps | grep nginx
curl -I http://localhost/health

# Check nginx logs
docker logs <nginx-container-id> --tail=100

# Verify nginx can reach upstreams
docker exec -it <nginx-container-id> curl -I http://prosaas-api:5000/health
```

## Verification Checklist

- [ ] All previous containers stopped and removed
- [ ] Network `prosaas-net` exists
- [ ] Configuration builds without errors
- [ ] All containers start and reach healthy state
- [ ] nginx responds to health check
- [ ] No port conflicts on host
- [ ] Services can communicate within Docker network
- [ ] Website loads correctly
- [ ] No 521 errors from Cloudflare
- [ ] No Restart loops in container status

## Notes

- This fix addresses the port conflict issue described in the Hebrew problem statement
- The configuration now follows Docker best practices for production deployments
- Only nginx should expose ports to the host - all other services communicate via the internal Docker network
- The `expose` directive makes ports available within the Docker network but doesn't publish them to the host
