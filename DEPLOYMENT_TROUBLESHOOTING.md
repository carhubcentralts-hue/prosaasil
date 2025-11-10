# 🚨 Deployment Stuck - Troubleshooting Guide

## Problem: Publishing Stuck at "Provision" or "Build"

### Common Causes:

#### 1. **Build Timeout** (Most Likely!)
Heavy Python packages (numpy, scipy, reportlab) take 2-3 minutes to compile.
Replit Cloud Run has build timeout limits.

**Solution:**
- ✅ Optimized `build_production.sh` with better progress logging
- ✅ Added `--no-cache-dir` to speed up pip
- ✅ Added quiet mode for npm (less output = faster)

#### 2. **Port Configuration Issue**
Replit expects:
- Single external port (80)
- Internal port NOT on localhost (0.0.0.0)

**Current Config** (from .replit):
```
[[ports]]
localPort = 5000
externalPort = 80
```

**Runtime** (from start_production.sh):
```bash
uvicorn asgi:app --host 0.0.0.0 --port ${PORT}
```
✅ This is CORRECT!

#### 3. **Heavy Dependencies**
Current heavy packages:
- numpy (60-90 sec compile)
- scipy (60-90 sec compile)
- reportlab (30 sec compile)

**Total build time: ~3-5 minutes**

### 🔧 Immediate Actions:

#### Option 1: Try Publishing Again
The optimized build script should work better now:
1. Cancel current stuck deployment
2. Click "Publish" again
3. Watch the Logs tab for progress

#### Option 2: Test Build Locally First
```bash
./test_build_locally.sh
```
This runs the build locally and shows timing for each phase.

#### Option 3: Simplify Dependencies (Advanced)
If build keeps timing out, consider:
- Remove numpy/scipy if not critical
- Use pre-built wheels
- Split into microservices

### 📊 Expected Build Timeline:

```
Phase 1: Python packages  → 2-3 minutes (numpy, scipy)
Phase 2: Frontend build   → 30-60 seconds
Phase 3: Baileys install  → 30 seconds
─────────────────────────────────────────────
TOTAL:                     → 3-5 minutes
```

### 🔍 How to Debug:

1. **Check Logs** in Replit Publishing UI:
   - Click "Logs" tab
   - Look for errors or where it stops

2. **Common Error Messages:**
   - "Timeout" → Build taking too long
   - "Port error" → Port config wrong (but yours is correct!)
   - "Command failed" → Build script error

3. **If Stuck at Provision:**
   - This is BEFORE build starts
   - Usually means Replit infrastructure issue
   - Wait 2-3 minutes or try again

4. **If Stuck at Build:**
   - Build is running but taking too long
   - Check if numpy/scipy are compiling (they take time!)
   - Wait up to 5 minutes before canceling

### ✅ Next Steps:

1. **Cancel** the current stuck deployment
2. **Wait** 1-2 minutes
3. **Try again** - new optimized build should work

If it still fails after 2-3 attempts:
- Run `./test_build_locally.sh` to test
- Check if packages install correctly
- Consider reducing dependencies
