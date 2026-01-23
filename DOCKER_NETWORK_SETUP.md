# Docker Network Setup for ProSaaS

## Required Network Creation

Before running `docker compose up`, you **MUST** create the external network.

### Automated Setup (Recommended)

Use the provided script to ensure the network exists:

```bash
# Run the network setup script
./scripts/ensure_docker_network.sh
```

This script will:
- Check if the network exists
- Create it if needed
- Support custom network names via `DOCKER_NETWORK_NAME` environment variable

### Manual Setup

Alternatively, create the network manually:

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
# Create network using the script (recommended)
./scripts/ensure_docker_network.sh

# Or manually
docker network create prosaas-net || true

# Start services
docker compose up -d
```

### Production
```bash
# Create network using the script (recommended)
./scripts/ensure_docker_network.sh

# Or manually
docker network create prosaas-net || true

# Start production services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Custom Network Name

If you want to use a custom network name:

```bash
# Set environment variable
export DOCKER_NETWORK_NAME=custom-net

# Run the script
./scripts/ensure_docker_network.sh

# Start services (the network name is read from .env or environment)
docker compose up -d
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
