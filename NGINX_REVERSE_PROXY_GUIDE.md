# Nginx Reverse Proxy Architecture

## Overview

This project now uses a dedicated Nginx reverse proxy container as the single entry point for all external traffic. This architecture provides:

- **Stability**: No port conflicts between services
- **Scalability**: Easy to add more services behind the proxy
- **Security**: Internal services are not exposed directly to the internet
- **WebSocket Support**: Proper handling of WebSocket connections for n8n and backend
- **SSL/TLS**: Centralized SSL termination (production)

## Architecture Diagram

```
Internet
    ↓
[Nginx Reverse Proxy] :80, :443
    ├── prosaas.pro → [Frontend Container] :80 (static files)
    ├── prosaas.pro/api → [Backend Container] :5000 (API)
    ├── prosaas.pro/ws → [Backend Container] :5000 (WebSocket)
    └── n8n.prosaas.pro → [n8n Container] :5678 (with WebSocket)
```

## Key Changes

### Before
- **Frontend**: Exposed port 80, included routing config
- **Backend**: Exposed port 5000
- **n8n**: Exposed port 5678
- **Issue**: Port conflicts, instability, 522 errors on Cloudflare

### After
- **Nginx**: Only container exposed on ports 80/443
- **Frontend**: Internal only, serves static files
- **Backend**: Internal only (port 5000)
- **n8n**: Internal only (port 5678)
- **Result**: Clean architecture, no port conflicts, stable WebSocket connections

## File Structure

```
docker/
├── nginx/
│   ├── nginx.conf                    # Main nginx configuration
│   ├── conf.d/
│   │   ├── prosaas.conf             # HTTP routing (development)
│   │   └── prosaas-ssl.conf         # HTTPS routing (production)
│   └── frontend-static.conf         # Frontend static file serving
├── nginx.conf                        # Legacy (kept for reference)
└── nginx-ssl.conf                    # Legacy (kept for reference)

Dockerfile.nginx                      # Nginx reverse proxy Dockerfile
docker-compose.yml                    # Base configuration (HTTP)
docker-compose.prod.yml              # Production overrides (HTTPS)
```

## Running the Stack

### Development (HTTP only)

```bash
docker compose up -d
```

This starts:
- Nginx reverse proxy on port 80
- All services in internal network
- Access via: http://prosaas.pro and http://n8n.prosaas.pro

### Production (HTTPS)

#### Option 1: Cloudflare Full (strict) with Origin Certificates

1. Generate origin certificates in Cloudflare Dashboard
2. Place certificates on the server:
   ```bash
   /opt/prosaasil/docker/nginx/ssl/prosaas-origin.crt
   /opt/prosaasil/docker/nginx/ssl/prosaas-origin.key
   ```
3. Start with production configuration:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

#### Option 2: Cloudflare Full (HTTP origin)

If you want Cloudflare to handle SSL and talk to the origin via HTTP:

1. Use the base docker-compose.yml (no prod override needed)
2. Set Cloudflare SSL mode to "Full" (not strict)
3. Start services:
   ```bash
   docker compose up -d
   ```

## Domain Routing

### prosaas.pro
- `/` → Frontend (React SPA)
- `/api/*` → Backend API
- `/ws/*` → Backend WebSocket (Twilio)
- `/webhook` → Backend webhooks
- `/assets` → Frontend static assets (cached)

### n8n.prosaas.pro
- `/` → n8n interface
- `/rest/push` → n8n WebSocket (real-time updates)
- All endpoints → Full WebSocket support

## Healthchecks

All services now include healthchecks:

- **Nginx**: Checks `/health` endpoint
- **Backend**: Checks `/api/health` endpoint  
- **Frontend**: Checks root `/` endpoint
- **n8n**: Startup check (no specific health endpoint)

The nginx service depends on backend and frontend being healthy before starting.

## Restart Policy

All services use `restart: unless-stopped` to ensure:
- Automatic restart on failure
- Persistent operation across server reboots
- Can be manually stopped without auto-restart

## WebSocket Configuration

### Backend WebSocket (/ws/)
- HTTP/1.1 upstream
- Upgrade/Connection headers
- Twilio subprotocol negotiation support
- Long timeouts (3600s)

### n8n WebSocket (all endpoints)
- HTTP/1.1 upstream (not HTTP/2 for stability)
- Upgrade/Connection headers
- Extra long timeouts (3600s)
- Buffering disabled
- Fixes code=1006 disconnection issues

## SSL/TLS Configuration (Production)

When using `docker-compose.prod.yml`:

1. **TLS Versions**: TLSv1.2, TLSv1.3
2. **Ciphers**: Modern ECDHE ciphers
3. **HSTS**: Enabled (31536000 seconds)
4. **Session Cache**: Shared 10MB cache
5. **HTTP/2**: Enabled for main site, disabled for n8n (WebSocket stability)

## Troubleshooting

### Port 80 already in use
```bash
# Check what's using port 80
sudo lsof -i :80

# Stop the conflicting service or kill the process
sudo systemctl stop nginx  # if system nginx is running
```

### Services not accessible
```bash
# Check all containers are running
docker compose ps

# Check nginx logs
docker compose logs nginx

# Check specific service
docker compose logs backend
```

### WebSocket disconnections (code=1006)
- Verify nginx is proxying with HTTP/1.1
- Check timeout settings are long enough (3600s)
- Ensure buffering is disabled for WebSocket endpoints

### SSL certificate errors
```bash
# Verify certificates exist on the server
ls -la /opt/prosaasil/docker/nginx/ssl/

# Check certificate validity
openssl x509 -in /opt/prosaasil/docker/nginx/ssl/prosaas-origin.crt -text -noout

# Check nginx configuration
docker compose exec nginx nginx -t
```

## Updating the Stack

```bash
# Pull latest images
docker compose pull

# Rebuild custom images
docker compose build

# Restart with zero downtime (if using multiple replicas)
docker compose up -d --no-deps --build nginx

# Or restart everything
docker compose down
docker compose up -d
```

## Security Notes

1. **No External Exposure**: Only nginx exposes ports 80/443
2. **Internal Network**: All services communicate via Docker network
3. **SSL Termination**: Nginx handles SSL/TLS
4. **Secrets**: Never commit certificates or .env files
5. **Headers**: Security headers enabled (HSTS, X-Frame-Options, etc.)

## Monitoring

Check service health:
```bash
# All services status
docker compose ps

# Nginx access logs
docker compose logs -f nginx

# Backend logs
docker compose logs -f backend

# n8n logs
docker compose logs -f n8n
```

## Migration from Old Setup

If you're upgrading from the old architecture:

1. **Backup** your data volumes
2. **Stop** the old containers: `docker compose down`
3. **Pull** latest code with new configuration
4. **Update** .env if needed
5. **Start** with new architecture: `docker compose up -d`
6. **Verify** all domains are accessible
7. **Test** WebSocket connections (n8n interface should not show connection errors)

## Development vs Production

| Aspect | Development | Production |
|--------|-------------|------------|
| SSL | HTTP only | HTTPS (port 443) |
| Config File | prosaas.conf | prosaas-ssl.conf |
| Certificates | Not needed | Required in /opt/prosaasil/docker/nginx/ssl/ |
| Compose File | docker-compose.yml | docker-compose.yml + docker-compose.prod.yml |
| Cloudflare SSL | Flexible | Full or Full (strict) |

## Support

For issues or questions:
1. Check logs: `docker compose logs [service]`
2. Verify configuration: `docker compose config`
3. Test nginx config: `docker compose exec nginx nginx -t`
4. Review this documentation

---

**Last Updated**: 2026-01-08  
**Architecture Version**: 2.0 (Dedicated Reverse Proxy)
