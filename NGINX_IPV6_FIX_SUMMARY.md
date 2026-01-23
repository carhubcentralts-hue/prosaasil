# Nginx IPv6 Listen Configuration Fix

## Problem Statement

The nginx configurations across the ProSaaS application were missing IPv6 listen directives, causing connection refused errors when clients tried to connect via IPv6 or when Docker's networking stack preferred IPv6. The specific symptom was:

```
❌ curl/wget http://localhost:80 → Connection refused
```

Even though:
- nginx master + worker processes existed
- `nginx -t` showed configuration was valid
- The service appeared to be running

## Root Cause

Nginx was only configured with `listen 80;` which by default binds to IPv4 (0.0.0.0:80). Without the explicit `listen [::]:80;` directive, nginx would not listen on IPv6 addresses, causing connection failures in environments where:
- IPv6 is preferred by the networking stack
- Docker's internal DNS resolves to IPv6 addresses
- Clients connect via IPv6

## Solution

Added explicit IPv6 listen directives to all nginx server blocks across three configuration files.

### Files Modified

#### 1. `docker/nginx/frontend-static.conf` (Frontend Container)
```nginx
server {
    listen 80;           # IPv4
    listen [::]:80;      # IPv6 - ADDED
    server_name _;
    # ...
}
```

Also added a `/health` endpoint for healthcheck support:
```nginx
location /health {
    access_log off;
    return 200 'ok';
    add_header Content-Type text/plain;
}
```

#### 2. `docker/nginx.conf` (Reverse Proxy - HTTP)
```nginx
# Main site
server {
    listen 80 default_server;
    listen [::]:80 default_server;  # IPv6 - ADDED
    # ...
}

# n8n subdomain
server {
    listen 80;
    listen [::]:80;  # IPv6 - ADDED
    # ...
}
```

#### 3. `docker/nginx-ssl.conf` (Reverse Proxy - HTTPS)
```nginx
# Main site - HTTP redirect
server {
    listen 80 default_server;
    listen [::]:80 default_server;  # IPv6 - ADDED
    # ...
}

# Main site - HTTPS
server {
    listen 443 ssl http2 default_server;
    listen [::]:443 ssl http2 default_server;  # IPv6 - ADDED
    # ...
}

# n8n - HTTP redirect
server {
    listen 80;
    listen [::]:80;  # IPv6 - ADDED
    # ...
}

# n8n - HTTPS
server {
    listen 443 ssl;
    listen [::]:443 ssl;  # IPv6 - ADDED
    # ...
}
```

## Verification

To verify nginx is now listening on both IPv4 and IPv6:

### Inside Frontend Container
```bash
# Check configuration syntax
docker exec -it prosaasil-frontend-1 nginx -t

# Check what ports nginx is listening on
docker exec -it prosaasil-frontend-1 ss -lntp
# OR
docker exec -it prosaasil-frontend-1 netstat -lntp

# Expected output should show:
# tcp  LISTEN  0.0.0.0:80    (IPv4)
# tcp  LISTEN     [::]:80    (IPv6)
```

### Inside Nginx Reverse Proxy Container
```bash
# Check configuration syntax
docker exec -it prosaasil-nginx-1 nginx -t

# Check listening ports
docker exec -it prosaasil-nginx-1 ss -lntp

# Expected output should show:
# tcp  LISTEN  0.0.0.0:80     (IPv4)
# tcp  LISTEN     [::]:80     (IPv6)
# tcp  LISTEN  0.0.0.0:443    (IPv4 - if SSL enabled)
# tcp  LISTEN     [::]:443    (IPv6 - if SSL enabled)
```

### Test Connectivity
```bash
# Test IPv4
docker exec -it prosaasil-frontend-1 curl -4 http://localhost/

# Test IPv6
docker exec -it prosaasil-frontend-1 curl -6 http://localhost/

# Test health endpoint
docker exec -it prosaasil-frontend-1 curl http://localhost/health
# Should return: ok
```

## Deployment Instructions

### Development Environment
```bash
# Rebuild and restart frontend container
docker compose up -d --build --force-recreate frontend

# Rebuild and restart nginx reverse proxy
docker compose up -d --build --force-recreate nginx
```

### Production Environment
```bash
# Rebuild and restart with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --force-recreate frontend nginx

# Check health status
docker inspect --format='{{json .State.Health}}' prosaasil-frontend-1
docker inspect --format='{{json .State.Health}}' prosaasil-nginx-1
```

## Benefits

1. **Better Compatibility**: Supports both IPv4 and IPv6 clients
2. **Docker Networking**: Resolves issues with Docker's dual-stack networking
3. **Future-Proof**: Ready for IPv6-only environments
4. **Reliability**: Prevents "connection refused" errors in diverse network configurations

## Testing Checklist

- [ ] Frontend container starts successfully
- [ ] Nginx reverse proxy starts successfully
- [ ] Health checks pass for frontend (`/health` returns 200)
- [ ] Health checks pass for nginx reverse proxy (`/health` returns 200)
- [ ] Can connect to frontend via IPv4 (`curl -4`)
- [ ] Can connect to frontend via IPv6 (`curl -6`)
- [ ] API requests work through reverse proxy
- [ ] WebSocket connections work
- [ ] SSL/TLS works (if using production config)

## Related Documentation

- See [docker-compose.yml](docker-compose.yml) for frontend service configuration
- See [docker-compose.prod.yml](docker-compose.prod.yml) for production overrides
- See [Dockerfile.frontend](Dockerfile.frontend) for frontend container build process
- See [Dockerfile.nginx](Dockerfile.nginx) for nginx reverse proxy build process

## References

- [Nginx listen directive documentation](http://nginx.org/en/docs/http/ngx_http_core_module.html#listen)
- [Docker IPv6 networking](https://docs.docker.com/config/daemon/ipv6/)
- Original issue: nginx inside frontend container refusing connections on port 80
