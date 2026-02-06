"""
server/config — Single Source of Truth for Configuration
=============================================================
All environment variables are loaded here with safe defaults.
No other module should call os.getenv / os.environ directly.

Secrets (tokens, keys) come ONLY from env vars — no defaults.
Non-secret operational settings have sensible defaults.
"""

import os

from .calls import SIMPLE_MODE


def _env(key: str, default: str | None = None) -> str | None:
    """Read an environment variable (single access point)."""
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    """Read an int env var with fallback."""
    val = _env(key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return default


def _env_bool(key: str, default: bool) -> bool:
    """Read a boolean env var (true/1/yes → True)."""
    val = _env(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes")


# ─── Baileys / WhatsApp Sharding ──────────────────────────
BAILEYS_SHARDS: int = _env_int("BAILEYS_NUM_SHARDS", 1)
BAILEYS_PORT: int = _env_int("BAILEYS_PORT", 3300)
BAILEYS_BASE_URL_TEMPLATE: str = _env(
    "BAILEYS_BASE_URL_TEMPLATE", "http://baileys-{shard}:{port}"
)

# Legacy single-shard fallback (used only when BAILEYS_SHARDS == 1)
BAILEYS_BASE_URL_LEGACY: str = _env(
    "BAILEYS_BASE_URL", f"http://baileys:{BAILEYS_PORT}"
)

# ─── Calls ─────────────────────────────────────────────────
MAX_CONCURRENT_CALLS: int = _env_int("MAX_CONCURRENT_CALLS", 50)
# MAX_ACTIVE_CALLS is an alias used by calls_capacity.py (same purpose as MAX_CONCURRENT_CALLS)
MAX_ACTIVE_CALLS: int = _env_int("MAX_ACTIVE_CALLS", MAX_CONCURRENT_CALLS)
CALLS_OVER_CAPACITY_BEHAVIOR: str = _env("CALLS_OVER_CAPACITY_BEHAVIOR", "reject")

# ─── Metrics ───────────────────────────────────────────────
METRICS_ENABLED: bool = _env_bool("METRICS_ENABLED", True)
METRICS_TOKEN: str | None = _env("METRICS_TOKEN")  # secret — no default

# ─── Redis ─────────────────────────────────────────────────
REDIS_URL: str = _env("REDIS_URL", "redis://redis:6379/0")

# ─── Production ────────────────────────────────────────────
PRODUCTION: bool = _env("PRODUCTION", "0") == "1"
FLASK_ENV: str = _env("FLASK_ENV", "development")
LOG_LEVEL: str = _env("LOG_LEVEL", "INFO")

# ─── Internal secrets (env only, no defaults) ─────────────
INTERNAL_SECRET: str | None = _env("INTERNAL_SECRET")

__all__ = [
    'SIMPLE_MODE',
    'BAILEYS_SHARDS', 'BAILEYS_PORT', 'BAILEYS_BASE_URL_TEMPLATE',
    'BAILEYS_BASE_URL_LEGACY',
    'MAX_CONCURRENT_CALLS', 'MAX_ACTIVE_CALLS',
    'METRICS_ENABLED', 'METRICS_TOKEN',
    'REDIS_URL', 'PRODUCTION', 'FLASK_ENV', 'LOG_LEVEL',
    'INTERNAL_SECRET',
]
