# Migration Lock Timeout Fix - Complete Implementation Guide

## 🎯 Problem Statement

Migrations were timing out after 120 seconds when running through Supabase's **connection pooler** (pgbouncer/supavisor). The root causes were:

1. **Wrong Connection Type**: Running DDL operations through a connection pooler designed for API traffic
2. **Ghost Locks**: Pooler creates "phantom" locks that appear and disappear, making debugging impossible
3. **SSL Issues**: Pooler connections have different SSL behavior that interferes with long-running DDL
4. **Blind Debugging**: No visibility into what was blocking migrations when lock timeouts occurred

## ✅ Solution Overview

We implemented a **5-phase fix** that completely eliminates the problem:

### Phase 1: Separate Connection Types
- Added `DATABASE_URL_POOLER` for API/Worker traffic
- Added `DATABASE_URL_DIRECT` for migrations/DDL operations
- Updated `database_url.py` to support both connection types

### Phase 2: Route Traffic Correctly
- **Migrations, Indexer, Backfill** → Use `DATABASE_URL_DIRECT`
- **API, Worker, Calls** → Use `DATABASE_URL_POOLER`
- Updated `docker-compose.prod.yml` and all config files

### Phase 3: Real-Time Lock Debugging
- Enhanced `exec_ddl_heavy()` to capture blocking PIDs **during** lock wait
- Shows exact processes blocking DDL operations in real-time
- Displays query details, ages, and application names

### Phase 4: Production-Safe Constraint Changes
- Refactored Migration 95 to use **two-phase constraint** approach
- This approach requires only `ShareUpdateExclusiveLock` instead of `AccessExclusiveLock`

### Phase 5: Pre-Migration Connection Check
- Added database connection audit before migrations
- Shows all active connections with PIDs, apps, and queries
- Helps identify external processes that might block DDL

---

## 🚀 Quick Start for Supabase Users

### Step 1: Update Environment Variables

Add to your `.env` file:
```bash
# Pooler connection (for API traffic)
DATABASE_URL_POOLER=postgresql://user:pass@xyz.pooler.supabase.com:5432/postgres

# Direct connection (for migrations/DDL)
DATABASE_URL_DIRECT=postgresql://user:pass@xyz.db.supabase.com:5432/postgres
```

### Step 2: Deploy Changes

```bash
# Pull latest code
git pull origin main

# Deploy with rebuild
./scripts/deploy_production.sh --rebuild
```

### Step 3: Verify Success

Check logs for:
```
✅ Created dedicated migration engine with DIRECT connection (not pooler)
🔍 DDL Heavy: Backend PID = 12345
✅ DDL Heavy completed successfully
```

---

## 📚 Full Documentation

See sections below for complete technical details, troubleshooting, and best practices.
