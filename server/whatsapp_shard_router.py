"""
server/whatsapp_shard_router.py — Baileys Shard Routing (SSOT)
================================================================
Routes WhatsApp requests to the correct Baileys shard based on
the tenant's (Business) shard assignment.

Sharding strategy:
- Each Business has a `whatsapp_shard` column (int, default=1)
- Shard URL: BAILEYS_SHARD_{N}_URL env var, or computed from service name
- Fallback: hash(business_id) % N_SHARDS if shard not explicitly set

Usage:
    from server.whatsapp_shard_router import get_baileys_base_url
    url = get_baileys_base_url(business_id)
    # Returns e.g. "http://baileys-1:3300"
"""

import os
import hashlib
import logging

logger = logging.getLogger(__name__)

# Default number of Baileys shards
DEFAULT_NUM_SHARDS = int(os.environ.get("BAILEYS_NUM_SHARDS", "1"))

# Default Baileys port
BAILEYS_PORT = int(os.environ.get("BAILEYS_PORT", "3300"))


def _get_shard_url(shard_id: int) -> str:
    """
    Get the URL for a specific Baileys shard.
    Checks env var first, then falls back to docker service naming convention.
    """
    env_key = f"BAILEYS_SHARD_{shard_id}_URL"
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val.rstrip("/")

    # Docker service naming convention: baileys-1, baileys-2, etc.
    # For single shard (shard_id=1), also check legacy "baileys" service name
    if shard_id == 1 and DEFAULT_NUM_SHARDS == 1:
        return os.environ.get("BAILEYS_BASE_URL", f"http://baileys:{BAILEYS_PORT}")

    return f"http://baileys-{shard_id}:{BAILEYS_PORT}"


def _hash_shard(business_id: int, num_shards: int) -> int:
    """Deterministic shard assignment via hash. Returns 1-based shard ID."""
    h = hashlib.md5(str(business_id).encode()).hexdigest()
    return (int(h, 16) % num_shards) + 1


def get_baileys_base_url(business_id: int, whatsapp_shard: int | None = None) -> str:
    """
    Get the Baileys service URL for a given business.

    Args:
        business_id: The Business ID
        whatsapp_shard: Explicit shard assignment from Business table.
                        If None, falls back to hash-based routing.

    Returns:
        Base URL for the Baileys shard (e.g. "http://baileys-1:3300")
    """
    num_shards = DEFAULT_NUM_SHARDS

    if whatsapp_shard and whatsapp_shard > 0:
        shard_id = whatsapp_shard
    else:
        shard_id = _hash_shard(business_id, num_shards)

    url = _get_shard_url(shard_id)
    logger.debug("Business %d → shard %d → %s", business_id, shard_id, url)
    return url


def get_all_shard_urls() -> dict[int, str]:
    """Return a map of shard_id → URL for all configured shards."""
    return {i: _get_shard_url(i) for i in range(1, DEFAULT_NUM_SHARDS + 1)}
