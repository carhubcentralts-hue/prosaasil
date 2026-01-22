# Docker Network Setup for ProSaaS

## Required Network Creation

Before running `docker compose up`, you **MUST** create the external network:

```bash
docker network create prosaas-net || true
```

The `|| true` ensures the command succeeds even if the network already exists.

## Why External Network?

Both `docker-compose.yml` and `docker-compose.prod.yml` are configured to use an external network:

```yaml
networks:
  prosaas-net:
    external: true
    name: prosaas-net
```

This configuration:
- ✅ Prevents network recreation warnings
- ✅ Ensures all services are on the same network
- ✅ Allows services to find each other via DNS (e.g., `prosaas-api`, `prosaas-calls`)
- ✅ Enables nginx to resolve service names at runtime

## Deployment Commands

### Development
```bash
# Create network (one time)
docker network create prosaas-net || true

# Start services
docker compose up -d
```

### Production
```bash
# Create network (one time)
docker network create prosaas-net || true

# Start production services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Error: "network prosaas-net not found"
```bash
docker network create prosaas-net
```

### Error: "network prosaas-net exists but was not created for project"
This means `external: true` is missing or the network wasn't pre-created. Solution:
```bash
docker network create prosaas-net || true
docker compose down
docker compose up -d
```

### Check Network Status
```bash
# List networks
docker network ls | grep prosaas-net

# Inspect network
docker network inspect prosaas-net

# List containers on network
docker network inspect prosaas-net -f '{{range .Containers}}{{.Name}} {{end}}'
```

## Network Configuration Summary

- **Network Name**: `prosaas-net`
- **Type**: External (pre-created)
- **Driver**: bridge (default)
- **Services**: nginx, redis, frontend, worker, prosaas-api, prosaas-calls, baileys, n8n
