# Architecture Diagram - Reverse Proxy Setup

## Network Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           INTERNET                                   │
│                     (Cloudflare Edge)                                │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      HOST MACHINE                                    │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │           Nginx Reverse Proxy Container                      │   │
│  │                (prosaas-nginx)                               │   │
│  │                                                              │   │
│  │  Ports: 80:80, 443:443                                      │   │
│  │                                                              │   │
│  │  Routes:                                                     │   │
│  │  • prosaas.pro → forward to frontend & backend              │   │
│  │  • n8n.prosaas.pro → forward to n8n                         │   │
│  └────────┬─────────────────────────────────┬──────────────────┘   │
│           │                                  │                       │
│           │    Docker Network (prosaas-network)                     │
│  ┌────────┴────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   Frontend      │  │    Backend       │  │      n8n         │  │
│  │  (prosaas-      │  │  (prosaas-       │  │  (prosaas-n8n)   │  │
│  │   frontend)     │  │   backend)       │  │                  │  │
│  │                 │  │                  │  │  Internal Port:  │  │
│  │  Internal Port: │  │  Internal Port:  │  │  5678            │  │
│  │  80             │  │  5000            │  │                  │  │
│  │                 │  │                  │  │  WebSocket       │  │
│  │  Serves:        │  │  Serves:         │  │  Support ✓       │  │
│  │  • Static HTML  │  │  • REST API      │  │                  │  │
│  │  • React SPA    │  │  • WebSocket     │  │  Automation      │  │
│  │  • Assets       │  │  • Webhooks      │  │  Platform        │  │
│  │                 │  │                  │  │                  │  │
│  │  No External    │  │  No External     │  │  No External     │  │
│  │  Port ✓         │  │  Port ✓          │  │  Port ✓          │  │
│  └─────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                      │
│  ┌──────────────────┐                                               │
│  │    Baileys       │                                               │
│  │  (prosaas-       │                                               │
│  │   baileys)       │                                               │
│  │                  │                                               │
│  │  Port: 3300      │                                               │
│  │  (debugging)     │                                               │
│  └──────────────────┘                                               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Request Flow Examples

### Example 1: Loading the Frontend

```
User Browser
    ↓ https://prosaas.pro
Cloudflare Edge (SSL)
    ↓ https://your-server.com
Nginx Reverse Proxy
    ↓ http://prosaas-frontend:80
Frontend Container
    ↓ Returns: index.html, React app
Nginx → Cloudflare → User
```

### Example 2: API Request

```
User Browser (React App)
    ↓ fetch('https://prosaas.pro/api/users')
Cloudflare Edge
    ↓
Nginx Reverse Proxy
    ↓ proxy_pass http://prosaas-backend:5000/api/users
Backend Container (Flask/FastAPI)
    ↓ Returns: JSON data
Nginx → Cloudflare → User
```

### Example 3: WebSocket Connection (n8n)

```
User Browser (n8n Interface)
    ↓ new WebSocket('wss://n8n.prosaas.pro/rest/push')
Cloudflare Edge (WebSocket upgrade)
    ↓
Nginx Reverse Proxy (WebSocket upgrade)
    ↓ Upgrade: websocket, Connection: upgrade
    ↓ proxy_pass http://prosaas-n8n:5678/rest/push
n8n Container
    ↓ Accepts WebSocket connection
    ↓ Real-time bidirectional communication
Persistent connection (timeout: 3600s)
```

## Port Usage Comparison

### ❌ Old Architecture (PROBLEMATIC)

```
┌──────────────────────────────────────┐
│ Host Machine                         │
│                                      │
│ Frontend:80    ← Port Conflict!     │
│ Backend:5000                         │
│ n8n:5678                             │
│ Baileys:3300                         │
│                                      │
│ Issues:                              │
│ • Multiple services on port 80      │
│ • Direct exposure to internet       │
│ • No centralized SSL                │
│ • WebSocket timeouts               │
│ • 522 errors on restart             │
└──────────────────────────────────────┘
```

### ✅ New Architecture (STABLE)

```
┌──────────────────────────────────────┐
│ Host Machine                         │
│                                      │
│ Nginx:80,443  ← Single entry point  │
│   ↓                                  │
│   ├─→ Frontend:80 (internal)        │
│   ├─→ Backend:5000 (internal)       │
│   ├─→ n8n:5678 (internal)           │
│   └─→ Baileys:3300 (internal/debug) │
│                                      │
│ Benefits:                            │
│ ✓ No port conflicts                 │
│ ✓ Single SSL termination            │
│ ✓ Proper WebSocket support          │
│ ✓ Stable connections                │
│ ✓ Clean separation                  │
└──────────────────────────────────────┘
```

## Configuration Files Map

```
Repository Root
│
├── docker-compose.yml           ← Orchestrates all services
│   └── defines: nginx, backend, frontend, n8n, baileys
│
├── docker-compose.prod.yml      ← Production overrides (SSL)
│   └── adds: SSL certificates, resource limits
│
├── Dockerfile.nginx             ← Nginx container build
│   └── uses: nginx:alpine + config files
│
├── Dockerfile.frontend          ← Frontend container build
│   └── uses: nginx:alpine + static files
│
└── docker/
    ├── nginx/
    │   ├── nginx.conf           ← Main nginx config
    │   │   └── includes: conf.d/*.conf
    │   │
    │   ├── conf.d/
    │   │   ├── prosaas.conf     ← HTTP routing (dev)
    │   │   │   └── Routes: prosaas.pro, n8n.prosaas.pro
    │   │   │
    │   │   └── prosaas-ssl.conf ← HTTPS routing (prod)
    │   │       └── Same routes + SSL config
    │   │
    │   └── frontend-static.conf ← Frontend static files
    │       └── Serves: React SPA
    │
    ├── nginx.conf               ← Legacy (reference)
    └── nginx-ssl.conf           ← Legacy (reference)
```

## SSL/TLS Flow (Production)

```
┌─────────────────────────────────────────────────────────────┐
│                      SSL Termination                         │
│                                                              │
│  Client (Browser)                                           │
│      ↓ HTTPS (TLS 1.2/1.3)                                 │
│  Cloudflare Edge                                            │
│      ↓ HTTPS (Full/Strict mode)                            │
│  Nginx Reverse Proxy                                        │
│      ↓ Decrypt SSL                                          │
│      ↓ HTTP (internal Docker network)                      │
│  Backend Services                                           │
│      ↓ Process request                                      │
│      ↓ HTTP response                                        │
│  Nginx                                                      │
│      ↓ Encrypt SSL                                          │
│  Cloudflare                                                 │
│      ↓ HTTPS                                               │
│  Client (Browser)                                           │
│                                                              │
│  Certificates stored in: ./certs/                           │
│  • fullchain.pem                                            │
│  • privkey.pem                                              │
└─────────────────────────────────────────────────────────────┘
```

## Health Check Flow

```
Docker Compose Start
    ↓
Backend starts
    ↓ healthcheck: curl http://localhost:5000/api/health
    ↓ retries: 3, interval: 30s, timeout: 10s
    ✓ Backend HEALTHY
    
Frontend starts
    ↓ healthcheck: curl http://localhost/
    ↓ retries: 3, interval: 30s, timeout: 10s
    ✓ Frontend HEALTHY
    
n8n starts
    ↓ (no healthcheck, service_started)
    ✓ n8n RUNNING
    
Nginx starts (depends_on: backend, frontend)
    ↓ waits for backend & frontend to be HEALTHY
    ↓ healthcheck: curl http://localhost/health
    ✓ Nginx HEALTHY
    
All services ready ✓
    ↓
System accepts traffic
```

## Restart Behavior

```
Container Crash
    ↓
Docker detects exit
    ↓
restart: unless-stopped
    ↓
Automatic restart
    ↓
Healthcheck runs
    ↓
Service restored

Server Reboot
    ↓
Docker daemon starts
    ↓
restart: unless-stopped
    ↓
All containers start automatically
    ↓
Services available
```

---

**Architecture Version**: 2.0  
**Last Updated**: 2026-01-08
