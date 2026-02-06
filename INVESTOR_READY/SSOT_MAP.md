# SSOT Map — Single Source of Truth

## Frontend

| Concern | Source File | Notes |
|---------|-----------|-------|
| **User type & roles** | `client/src/types/api.ts` | `'system_admin' \| 'owner' \| 'admin' \| 'agent'` |
| **Auth context** | `client/src/features/auth/hooks.ts` | `useAuth()` hook |
| **Permission gating** | `client/src/features/permissions/` | Role-based access control |
| **HTTP client** | `client/src/services/http.ts` | `http.get/post/put/patch/delete` |
| **API request (React Query)** | `client/src/lib/queryClient.ts` | `apiRequest()` with JSON body |
| **Date formatting** | `client/src/shared/utils/format.ts` | `formatDate, formatDateOnly, formatTimeOnly, formatRelativeTime` |
| **Conversation display** | `client/src/shared/utils/conversation.ts` | `getConversationDisplayName, normalizePhoneForDisplay` |
| **Toast/notifications** | `client/src/shared/contexts/NotificationContext.tsx` | Single notification system |
| **Logger** | `client/src/shared/utils/logger.ts` | Dev-only logging, safe in production |
| **Lead types** | `client/src/pages/Leads/types.ts` | Lead, LeadStatus, LeadSource |
| **CSS utilities** | `client/src/shared/utils/cn.ts` | Tailwind class merging |

## Backend

| Concern | Source File | Notes |
|---------|-----------|-------|
| **Configuration SSOT** | `server/config/__init__.py` | All env vars, defaults, no scattered `os.getenv` |
| **Database models** | `server/models_sql.py` | All SQLAlchemy models |
| **Auth/session** | `server/ui/auth.py` | Session management, role decorators |
| **App factory** | `server/app_factory.py` | Flask app creation, security headers, CORS, metrics wiring |
| **Rate limiting** | `server/rate_limiter.py` | Presets: login, password, webhook, TTS |
| **AI agent factory** | `server/agent_tools/agent_factory.py` | Agent creation, model settings |
| **Phone normalization** | `server/agent_tools/phone_utils.py` | E.164 normalization |
| **Database URL** | `server/database_url.py` | Connection string handling |
| **Feature flags** | `server/services/feature_flags.py` | Central feature flag management |
| **Status mapping** | `server/services/status_service.py` | Lead status management |
| **WhatsApp provider** | `server/whatsapp_provider.py` | WhatsApp API abstraction (uses shard router) |
| **Queue definitions** | `server/queues.py` | All queue names, priorities, timeouts (SSOT) |
| **Metrics** | `server/metrics.py` | Operational counters/gauges, wired in app_factory |
| **Shard routing** | `server/whatsapp_shard_router.py` | Baileys shard assignment per tenant (SSOT) |
| **Call state** | `server/calls_state.py` | Redis-backed call session state |
| **Call capacity** | `server/services/calls_capacity.py` | Redis-backed call slot tracking (uses config SSOT) |
| **Health endpoints** | `server/health_endpoints.py` | All health/readiness probes |

## Scaling

| Concern | Source File | Notes |
|---------|-----------|-------|
| **Config SSOT** | `server/config/__init__.py` | Shards, concurrency, metrics — all defaults in code |
| **Queue SSOT** | `server/queues.py` | Queue names, worker groups, job defaults |
| **Shard SSOT** | `server/whatsapp_shard_router.py` | Baileys sharding routing logic |
| **Calls scaling** | `server/calls_state.py` + `server/services/calls_capacity.py` | Redis state + capacity |
| **Scaling plan** | `INVESTOR_READY/SCALING_PLAN.md` | Full horizontal scaling plan |

## Configuration

| Concern | Source File | Notes |
|---------|-----------|-------|
| **Environment** | `.env` (gitignored) | Secrets and overrides only |
| **Config SSOT** | `server/config/__init__.py` | Defaults in code, env overrides |
| **Docker (dev)** | `docker-compose.yml` | Development environment |
| **Docker (prod)** | `docker-compose.prod.yml` | Production overrides + multi-worker + shards |
| **CI/CD** | `.github/workflows/ci.yml` | All quality gates |
| **Quality gate** | `scripts/quality_gate.sh` | Unified quality gate script |
| **SSOT checks** | `scripts/no_duplicate_ssot_checks.sh` | Duplicate prevention gate |
| **Dependency policy** | `DEPENDENCY_POLICY.md` | Pinning and update strategy |
| **TypeScript** | `tsconfig.json` | Compiler options |
| **Vite** | `client/vite.config.ts` | Build configuration |
| **ESLint** | `client/.eslintrc.cjs` | Linting rules |
| **Prettier** | `client/.prettierrc` | Formatting rules |
