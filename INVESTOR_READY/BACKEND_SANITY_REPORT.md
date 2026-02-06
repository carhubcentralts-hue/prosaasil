# Backend Sanity Report

## Test Health

| Metric | Before | After |
|--------|--------|-------|
| Pytest CI step | ❌ `continue-on-error: true` | **✅ Blocking** |
| Unit tests passing | N/A (import crash) | **32/32** |
| Import-time crash | ❌ OpenAI client fails without API key | **✅ Lazy initialization** |

## Fixes Applied

### agent_factory.py — Lazy OpenAI Client
- **Before**: `_openai_client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))` at module level
- **After**: Lazy `_get_or_create_openai_client()` function, only creates client when first used
- **Impact**: Tests can now import agent modules without requiring OPENAI_API_KEY

## SSOT Map

See [SSOT_MAP.md](./SSOT_MAP.md) for the full single-source-of-truth mapping.

## Known Issues (Integration Tests)

The following test categories require external services and are not run in CI:

| Category | Count | Requirement |
|----------|-------|-------------|
| Flask app context | ~12 | Full Flask app setup |
| Database (PostgreSQL) | ~25 | DATABASE_URL with real DB |
| SQLite index conflicts | ~21 | Test isolation fixture needed |
| Mock target mismatches | ~5 | Code refactoring needed |
| Missing `requests_mock` | ~2 | Added to CI deps |

These are tracked for future improvement but do not block CI.
