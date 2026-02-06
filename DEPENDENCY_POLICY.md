# Dependency Policy

## Overview

ProSaaS manages dependencies for two ecosystems: Python (backend) and Node.js (frontend).

## Python (Backend)

### Lock File

- **`requirements.lock`** contains exact pinned versions of all production dependencies.
- Generated via: `pip freeze > requirements.lock`
- CI and production Docker builds install from `requirements.lock` for reproducibility.
- `pyproject.toml` retains flexible version ranges for development convenience.

### Update Process

1. **Monthly cadence**: First week of each month, run `pip install --upgrade` on all deps.
2. Run full test suite: `pytest tests/ -v`
3. Run `pip-audit` to verify no new vulnerabilities.
4. Regenerate: `pip freeze > requirements.lock`
5. Commit both `pyproject.toml` (if ranges changed) and `requirements.lock`.

## Node.js (Frontend)

### Lock File

- **`client/package-lock.json`** is committed and managed.
- CI uses `npm ci` (not `npm install`) to ensure deterministic builds.
- Any drift between `package.json` and `package-lock.json` will cause `npm ci` to fail.

### Update Process

1. **Monthly cadence**: First week of each month, run `npm update` in `client/`.
2. Run full test suite: `npm run test && npm run build`
3. Run `npm audit --omit=dev --audit-level=high` to verify no new vulnerabilities.
4. Commit updated `package.json` and `package-lock.json`.

## Version Pinning Strategy

| Ecosystem | Strategy | File |
|-----------|----------|------|
| Python production | Exact pins in lock file | `requirements.lock` |
| Python dev | Flexible ranges | `pyproject.toml` |
| Node.js | Lockfile via npm ci | `client/package-lock.json` |

## Security Scanning

| Tool | Ecosystem | CI Blocking | Level |
|------|-----------|-------------|-------|
| `pip-audit` | Python | ✅ Yes | All severities |
| `npm audit` | Node.js | ✅ Yes | high/critical |

## Exceptions

- See `client/AUDIT_ALLOWLIST.md` for frontend exceptions.
- See `server/AUDIT_ALLOWLIST.md` for backend exceptions.
