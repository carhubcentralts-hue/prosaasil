# 🚀 Quick Start Guide - Reverse Proxy Deployment

## תיאור בעברית

הפרויקט עבר לארכיטקטורה חדשה עם Reverse Proxy ייעודי. כל התעבורה החיצונית עוברת דרך קונטיינר Nginx אחד, מה שמונע קונפליקטים בפורטים ומבטיח יציבות.

**שינויים עיקריים:**
- ✅ Nginx אחד מאזין לפורטים 80/443
- ✅ כל השירותים האחרים פנימיים בלבד (ללא חשיפה חיצונית)
- ✅ תמיכה מלאה ב-WebSocket עבור n8n
- ✅ מדיניות restart אוטומטית
- ✅ Healthchecks לכל השירותים

## English Description

The project has been migrated to a new architecture with a dedicated Reverse Proxy. All external traffic goes through a single Nginx container, preventing port conflicts and ensuring stability.

**Key Changes:**
- ✅ Single Nginx listening on ports 80/443
- ✅ All other services are internal-only (no external exposure)
- ✅ Full WebSocket support for n8n
- ✅ Automatic restart policy
- ✅ Healthchecks for all services

---

## Prerequisites

- Docker installed
- Docker Compose v2+
- Ports 80 and 443 available

## Quick Deploy

### Development (HTTP)

```bash
# 1. Validate configuration
./validate_nginx_config.sh

# 2. Start services
docker compose up -d

# 3. Check status
docker compose ps

# 4. View logs
docker compose logs -f nginx
```

**Access:**
- Main app: http://prosaas.pro
- n8n: http://n8n.prosaas.pro

### Production (HTTPS)

```bash
# 1. Place SSL certificates on server
# Certificates should be located at:
# /opt/prosaasil/docker/nginx/ssl/prosaas-origin.crt
# /opt/prosaasil/docker/nginx/ssl/prosaas-origin.key

# 2. Validate configuration
./validate_nginx_config.sh

# 3. Start services with production config
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. Verify HTTPS
curl -I https://prosaas.pro
curl -I https://n8n.prosaas.pro
```

**Access:**
- Main app: https://prosaas.pro
- n8n: https://n8n.prosaas.pro

---

## Architecture Overview

```
Internet → Nginx Reverse Proxy → {
    prosaas.pro → Frontend + Backend API
    n8n.prosaas.pro → n8n (with WebSocket)
}
```

### Exposed Ports (External)
- **Nginx**: 80, 443

### Internal Ports (Docker Network)
- **Frontend**: 80
- **Backend**: 5000
- **n8n**: 5678
- **Baileys**: 3300 (optional debug)

---

## Common Commands

### Start/Stop
```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart specific service
docker compose restart nginx
```

### Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f nginx
docker compose logs -f backend
docker compose logs -f n8n
```

### Status Check
```bash
# Service status
docker compose ps

# Health check
curl http://localhost/health

# Nginx config test
docker compose exec nginx nginx -t
```

### Updates
```bash
# Pull latest images
docker compose pull

# Rebuild and restart
docker compose up -d --build
```

---

## Troubleshooting

### Port 80 Already in Use
```bash
# Check what's using the port
sudo lsof -i :80

# Stop conflicting service
sudo systemctl stop nginx  # if system nginx
```

### Container Not Starting
```bash
# Check logs
docker compose logs [service-name]

# Remove and recreate
docker compose down
docker compose up -d
```

### WebSocket Issues (n8n)
```bash
# Check nginx logs
docker compose logs nginx

# Verify nginx config
docker compose exec nginx nginx -t

# Restart nginx
docker compose restart nginx
```

### SSL Certificate Issues
```bash
# Verify certificates exist on server
ls -la /opt/prosaasil/docker/nginx/ssl/

# Check certificate validity
openssl x509 -in /opt/prosaasil/docker/nginx/ssl/prosaas-origin.crt -text -noout

# Check permissions
chmod 644 /opt/prosaasil/docker/nginx/ssl/*.{crt,key}
```

---

## Configuration Files

### Core Files
- **docker-compose.yml** - Base configuration (all services)
- **docker-compose.prod.yml** - Production overrides (SSL)
- **Dockerfile.nginx** - Nginx reverse proxy container
- **Dockerfile.frontend** - Frontend static files container

### Nginx Configuration
- **docker/nginx/nginx.conf** - Main nginx config
- **docker/nginx/conf.d/prosaas.conf** - HTTP routing
- **docker/nginx/conf.d/prosaas-ssl.conf** - HTTPS routing
- **docker/nginx/frontend-static.conf** - Frontend static serving

### Validation & Documentation
- **validate_nginx_config.sh** - Configuration validator
- **NGINX_REVERSE_PROXY_GUIDE.md** - Detailed guide
- **REVERSE_PROXY_IMPLEMENTATION_SUMMARY.md** - Implementation details
- **ARCHITECTURE_DIAGRAM.md** - Visual architecture

---

## Cloudflare Configuration

### Option 1: Full (Strict) - Recommended
1. Set SSL mode: **Full (strict)**
2. Generate Origin Certificate in Cloudflare
3. Place certificates on server at `/opt/prosaasil/docker/nginx/ssl/`
4. Use production compose: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

### Option 2: Full - Simpler
1. Set SSL mode: **Full**
2. No certificates needed in containers
3. Use base compose: `docker compose up -d`
4. Cloudflare handles SSL, origin uses HTTP

---

## Security Checklist

- [ ] Never commit `.env` files
- [ ] Never commit SSL certificates
- [ ] Keep `.gitignore` updated
- [ ] Use strong passwords in `.env`
- [ ] Regularly update Docker images
- [ ] Monitor container logs
- [ ] Set up log rotation
- [ ] Enable Cloudflare firewall rules

---

## Monitoring

### Health Checks
```bash
# Quick status
docker compose ps

# Detailed health
docker inspect prosaas-nginx | grep Health -A 10
docker inspect prosaas-backend | grep Health -A 10
docker inspect prosaas-frontend | grep Health -A 10
```

### Resource Usage
```bash
# Container stats
docker stats

# Disk usage
docker system df
```

### Logs
```bash
# Live tail all services
docker compose logs -f --tail=100

# Export logs
docker compose logs > logs.txt
```

---

## Backup & Restore

### Backup
```bash
# Backup volumes
docker run --rm -v prosaasil_n8n_data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/n8n_data.tar.gz /data
docker run --rm -v prosaasil_recordings_data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/recordings_data.tar.gz /data

# Backup environment
cp .env .env.backup
```

### Restore
```bash
# Restore volumes
docker run --rm -v prosaasil_n8n_data:/data -v $(pwd)/backup:/backup alpine tar xzf /backup/n8n_data.tar.gz -C /

# Restore environment
cp .env.backup .env
```

---

## Performance Tuning

### Nginx
- Worker processes: Auto-tuned to CPU count
- Keepalive connections: Enabled
- Gzip compression: Enabled
- HTTP/2: Enabled (main site)

### Backend
- Timeouts: 300s for downloads, 3600s for WebSocket
- Buffering: Disabled for streaming
- Connection pooling: Enabled

### Resource Limits (Production)
- **Nginx**: 0.5 CPU, 256MB RAM
- **Backend**: 2 CPU, 2GB RAM
- **Frontend**: 0.5 CPU, 256MB RAM
- **Baileys**: 1 CPU, 1GB RAM

---

## Support & Documentation

### Read First
1. **NGINX_REVERSE_PROXY_GUIDE.md** - Complete guide
2. **ARCHITECTURE_DIAGRAM.md** - Visual diagrams
3. **REVERSE_PROXY_IMPLEMENTATION_SUMMARY.md** - Technical details

### Getting Help
1. Run validation: `./validate_nginx_config.sh`
2. Check logs: `docker compose logs [service]`
3. Test nginx: `docker compose exec nginx nginx -t`
4. Review documentation above

---

## Migration from Old Setup

If upgrading:

```bash
# 1. Backup
docker compose down
docker run --rm -v prosaasil_n8n_data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/n8n_data.tar.gz /data

# 2. Pull new configuration
git pull

# 3. Start with new architecture
docker compose up -d

# 4. Verify
docker compose ps
curl http://localhost/health
```

---

## Status

✅ **Implementation Complete**  
✅ **Configuration Validated**  
✅ **Documentation Complete**  
✅ **Ready for Deployment**

**Version**: 2.0  
**Last Updated**: 2026-01-08  
**Architecture**: Dedicated Reverse Proxy

---

## Quick Links

- [Detailed Guide](NGINX_REVERSE_PROXY_GUIDE.md)
- [Architecture Diagrams](ARCHITECTURE_DIAGRAM.md)
- [Implementation Summary](REVERSE_PROXY_IMPLEMENTATION_SUMMARY.md)
- [Validation Script](validate_nginx_config.sh)
