"""
Tests for SSOT wiring: config, shard routing, metrics, calls state.
Validates that all new SSOT components work correctly.
"""
import os


# ─── Test 1: Config SSOT defaults ────────────────────────────────────────

def test_config_defaults():
    """Config module provides sensible defaults without any env vars."""
    # Clear env vars that might interfere
    saved = {}
    for key in ('BAILEYS_NUM_SHARDS', 'MAX_CONCURRENT_CALLS', 'METRICS_ENABLED'):
        saved[key] = os.environ.pop(key, None)

    try:
        # Re-import to test defaults
        import importlib
        import server.config
        importlib.reload(server.config)

        assert server.config.BAILEYS_SHARDS >= 1
        assert server.config.MAX_CONCURRENT_CALLS >= 1
        assert server.config.METRICS_ENABLED is True
        assert server.config.BAILEYS_PORT == 3300
        assert server.config.REDIS_URL.startswith("redis://")
    finally:
        for key, val in saved.items():
            if val is not None:
                os.environ[key] = val


# ─── Test 2: Shard routing - deterministic ────────────────────────────────

def test_shard_routing_deterministic():
    """Same business_id always maps to the same shard."""
    from server.whatsapp_shard_router import _hash_shard

    shard_a = _hash_shard(42, 4)
    shard_b = _hash_shard(42, 4)
    assert shard_a == shard_b, "Same business_id must map to the same shard"
    assert 1 <= shard_a <= 4, "Shard ID must be 1-based and within range"


def test_shard_routing_distribution():
    """With BAILEYS_SHARDS=2, different business IDs distribute across shards."""
    from server.whatsapp_shard_router import _hash_shard

    shards = {_hash_shard(bid, 2) for bid in range(1, 101)}
    assert shards == {1, 2}, "100 businesses should distribute across both shards"


def test_shard_routing_url_format():
    """get_baileys_base_url returns a URL string for a given business."""
    from server.whatsapp_shard_router import get_baileys_base_url

    url = get_baileys_base_url(business_id=1)
    assert url.startswith("http://"), f"Expected http URL, got: {url}"
    assert ":" in url, "URL should contain a port"


def test_shard_routing_explicit_shard():
    """Explicit whatsapp_shard overrides hash-based routing."""
    from server.whatsapp_shard_router import get_baileys_base_url

    url = get_baileys_base_url(business_id=1, whatsapp_shard=5)
    assert "baileys-5" in url, f"Expected shard 5 in URL, got: {url}"


def test_shard_routing_alias():
    """get_baileys_base_url_for_business is an alias for get_baileys_base_url."""
    from server.whatsapp_shard_router import (
        get_baileys_base_url,
        get_baileys_base_url_for_business,
    )

    assert get_baileys_base_url(42) == get_baileys_base_url_for_business(42)


# ─── Test 3: Metrics endpoint registration ───────────────────────────────

def test_metrics_endpoint_with_token():
    """When METRICS_TOKEN is set, /metrics.json returns 200 with valid token."""
    os.environ["METRICS_TOKEN"] = "test-secret-token"
    try:
        import importlib
        import server.config
        importlib.reload(server.config)

        from flask import Flask
        # Re-import metrics module to pick up new config
        import server.metrics
        importlib.reload(server.metrics)
        from server.metrics import register_metrics_endpoint

        app = Flask(__name__)
        register_metrics_endpoint(app)

        with app.test_client() as client:
            # Without token → 401
            resp = client.get("/metrics.json")
            assert resp.status_code == 401, f"Expected 401 without token, got {resp.status_code}"

            # With query param token → 200
            resp = client.get("/metrics.json?token=test-secret-token")
            assert resp.status_code == 200, f"Expected 200 with token, got {resp.status_code}"
            data = resp.get_json()
            assert "uptime_seconds" in data
            assert "counters" in data

            # With Bearer header → 200
            resp = client.get(
                "/metrics.json",
                headers={"Authorization": "Bearer test-secret-token"},
            )
            assert resp.status_code == 200
    finally:
        os.environ.pop("METRICS_TOKEN", None)
        import importlib
        import server.config
        importlib.reload(server.config)


def test_metrics_endpoint_without_token():
    """When no METRICS_TOKEN, endpoint allows open access (no token to check)."""
    os.environ.pop("METRICS_TOKEN", None)
    os.environ.pop("INTERNAL_SECRET", None)

    import importlib
    import server.config
    importlib.reload(server.config)

    import server.metrics
    importlib.reload(server.metrics)
    from server.metrics import register_metrics_endpoint

    from flask import Flask
    app = Flask(__name__)
    register_metrics_endpoint(app)

    with app.test_client() as client:
        resp = client.get("/metrics.json")
        # With empty token, the check is skipped → 200
        assert resp.status_code == 200


# ─── Test 4: Calls state manager ─────────────────────────────────────────

def test_calls_state_manager_init():
    """CallStateManager initializes with config defaults."""
    from server.calls_state import CallStateManager
    from server.config import MAX_CONCURRENT_CALLS

    mgr = CallStateManager(redis_client=None)
    assert mgr._max_concurrent == MAX_CONCURRENT_CALLS
    assert mgr._max_concurrent > 0, "Max concurrent must be positive"


# ─── Test 5: Config env override ─────────────────────────────────────────

def test_config_env_override():
    """Config respects environment variable overrides."""
    os.environ["BAILEYS_NUM_SHARDS"] = "4"
    os.environ["MAX_CONCURRENT_CALLS"] = "100"

    try:
        import importlib
        import server.config
        importlib.reload(server.config)

        assert server.config.BAILEYS_SHARDS == 4
        assert server.config.MAX_CONCURRENT_CALLS == 100
    finally:
        os.environ.pop("BAILEYS_NUM_SHARDS", None)
        os.environ.pop("MAX_CONCURRENT_CALLS", None)
        import server.config
        importlib.reload(server.config)
