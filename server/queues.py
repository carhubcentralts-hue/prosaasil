"""
server/queues.py — Single Source of Truth for Queue Definitions
================================================================
All queue names, priorities, and configurations are defined here.
Workers, enqueue calls, and compose files reference this module.
"""

# Queue definitions ordered by priority (highest first)
# Each queue has: name, priority (lower = higher priority), description
QUEUE_DEFINITIONS = [
    {"name": "high", "priority": 1, "description": "Realtime actions: WhatsApp send, critical webhooks, urgent notifications"},
    {"name": "default", "priority": 5, "description": "Standard background jobs: lead processing, AI responses"},
    {"name": "low", "priority": 10, "description": "Deferred tasks: reports, cleanup, indexing, analytics"},
    {"name": "media", "priority": 7, "description": "Attachment processing, transcoding, thumbnail generation"},
    {"name": "receipts", "priority": 5, "description": "Receipt sync and processing"},
    {"name": "receipts_sync", "priority": 5, "description": "Gmail receipt synchronization"},
    {"name": "maintenance", "priority": 10, "description": "System maintenance: stale cleanup, garbage collection"},
    {"name": "recordings", "priority": 7, "description": "Call recording download and processing"},
    {"name": "broadcasts", "priority": 8, "description": "WhatsApp broadcast message dispatch"},
]

# Queue name constants for use in enqueue calls
HIGH = "high"
DEFAULT = "default"
LOW = "low"
MEDIA = "media"
RECEIPTS = "receipts"
RECEIPTS_SYNC = "receipts_sync"
MAINTENANCE = "maintenance"
RECORDINGS = "recordings"
BROADCASTS = "broadcasts"

# All queue names as a list (used by workers and compose)
ALL_QUEUES = [q["name"] for q in QUEUE_DEFINITIONS]

# Comma-separated string for RQ_QUEUES env var
ALL_QUEUES_CSV = ",".join(ALL_QUEUES)

# Worker group assignments: which queues each worker type listens to
WORKER_GROUPS = {
    "worker-high": [HIGH],
    "worker-default": [DEFAULT, RECEIPTS, RECEIPTS_SYNC],
    "worker-low": [LOW, MAINTENANCE, BROADCASTS],
    "worker-media": [MEDIA, RECORDINGS],
    # Full worker (dev/legacy) — listens to all queues
    "worker": ALL_QUEUES,
}

# Default job timeouts and retries
JOB_DEFAULTS = {
    HIGH: {"timeout": 60, "ttl": 300, "retry_max": 3, "retry_interval": 5},
    DEFAULT: {"timeout": 300, "ttl": 600, "retry_max": 2, "retry_interval": 30},
    LOW: {"timeout": 900, "ttl": 3600, "retry_max": 1, "retry_interval": 60},
    MEDIA: {"timeout": 600, "ttl": 1800, "retry_max": 2, "retry_interval": 30},
    RECEIPTS: {"timeout": 300, "ttl": 600, "retry_max": 2, "retry_interval": 30},
    RECEIPTS_SYNC: {"timeout": 300, "ttl": 600, "retry_max": 2, "retry_interval": 30},
    MAINTENANCE: {"timeout": 600, "ttl": 3600, "retry_max": 1, "retry_interval": 60},
    RECORDINGS: {"timeout": 600, "ttl": 1800, "retry_max": 2, "retry_interval": 30},
    BROADCASTS: {"timeout": 600, "ttl": 1800, "retry_max": 2, "retry_interval": 30},
}

# Dead-letter queue for failed jobs
DEAD_LETTER_QUEUE = "dead_letter"

# Default worker concurrency (overridable via WORKER_CONCURRENCY env)
DEFAULT_WORKER_CONCURRENCY = 2


def get_job_config(queue_name: str) -> dict:
    """Get timeout/retry config for a queue."""
    return JOB_DEFAULTS.get(queue_name, JOB_DEFAULTS[DEFAULT])


def get_worker_queues(worker_name: str) -> list:
    """Get the list of queues for a specific worker type."""
    return WORKER_GROUPS.get(worker_name, ALL_QUEUES)
