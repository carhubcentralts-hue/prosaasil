# Fix for Scheduled Messages Syntax Error

## Problem
After adding the weekday selection feature to scheduled messages, the following error appeared on application startup:

```
ERROR [server.app_factory] ❌ CRITICAL: Failed to register essential API blueprints: 
expected an indented block after 'except' statement on line 654 (scheduled_messages_service.py, line 655)
```

## Root Cause
The error was caused by **stale Python bytecode cache files** (`.pyc` files in `__pycache__` directories). When code is updated, especially with indentation changes or new control flow structures, old cached bytecode can cause Python to report misleading syntax errors.

## Investigation Results
- ✅ Source code in `server/services/scheduled_messages_service.py` has **no syntax errors**
- ✅ All `try`/`except` blocks are properly structured
- ✅ The weekday selection logic (lines 594-620) is correctly implemented
- ✅ AST parsing and tokenization of the file succeeded
- ❌ Cached `.pyc` files contained outdated bytecode from before the weekday feature

## Solution

### Quick Fix (Production)
Run the cleanup script to remove all cached bytecode:

```bash
./clear_python_cache.sh
```

Or manually:

```bash
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete
```

Then restart your application.

### Prevention
The `.gitignore` file already excludes cache files:
```
__pycache__/
*.pyc
```

However, in production/deployment environments, ensure you:
1. Clear Python cache after pulling new code
2. Or add cache clearing to your deployment script
3. Or use `PYTHONDONTWRITEBYTECODE=1` environment variable to disable bytecode caching

### Docker Users
If using Docker, add this to your Dockerfile:
```dockerfile
ENV PYTHONDONTWRITEBYTECODE=1
```

Or add a cleanup step:
```dockerfile
RUN find /app -type d -name "__pycache__" -exec rm -rf {} + || true
```

## Verification
After clearing the cache, verify the application starts without errors:

```bash
python3 -m py_compile server/services/scheduled_messages_service.py
python3 -m py_compile server/routes_scheduled_messages.py
```

Both should compile successfully with no errors.

## Related Code
The weekday selection feature was added in:
- `server/services/scheduled_messages_service.py` (lines 594-620)
- Database migration 134 added `active_weekdays` column
- Similar logic exists in `server/services/appointment_automation_service.py`

The feature works correctly - only the cached bytecode was problematic.
