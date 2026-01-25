"""
Unified Bulk Operation Gate - Prevents Massive Enqueue
======================================================

This module provides a unified gate for ALL bulk operations to prevent
API/UI from creating too many jobs too fast.

Key Features:
- Deduplication: Prevents duplicate jobs for same operation
- Rate limiting: Limits enqueues per business per operation type
- Business-level locks: One active job per business per operation type
- Redis-based: Works across multiple app instances

Usage:
    from server.services.bulk_gate import BulkGate
    
    gate = BulkGate(redis_conn)
    
    # Check if operation is allowed
    allowed, reason = gate.can_enqueue(
        business_id=123,
        operation_type='delete_leads_bulk',
        user_id=456
    )
    
    if not allowed:
        return jsonify({"error": reason}), 429
    
    # Acquire lock and enqueue
    lock_acquired = gate.acquire_lock(
        business_id=123,
        operation_type='delete_leads_bulk'
    )
    
    if lock_acquired:
        # Enqueue to RQ
        queue.enqueue(job_function, ...)
        return jsonify({"job_id": ...}), 202
"""
import time
import logging
from typing import Tuple, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BulkGate:
    """
    Unified gate for bulk operations - prevents enqueue flooding
    
    Rules enforced:
    1. Max 1 active job per business per operation type (lock per operation)
    2. Rate limit: Max N enqueues per minute per business per operation
    3. Deduplication: Same params within cooldown period
    
    NOTE: Lock is per business_id:operation_type - different operations
    can run simultaneously for the same business.
    """
    
    # Rate limits per operation type (enqueues per minute)
    RATE_LIMITS = {
        'delete_leads_bulk': 2,           # Max 2 delete operations per minute
        'update_leads_bulk': 5,           # Max 5 update operations per minute
        'delete_receipts_all': 1,         # Max 1 receipt deletion per minute
        'delete_imported_leads': 2,       # Max 2 import delete per minute
        'broadcast_whatsapp': 3,          # Max 3 broadcasts per minute
        'export_receipts': 5,             # Max 5 exports per minute
        'enqueue_outbound_calls': 2,      # Max 2 bulk call enqueues per minute
        'default': 10                     # Default for unlisted operations
    }
    
    # Lock TTL (seconds) - how long a job "owns" an operation type
    LOCK_TTL = {
        'delete_leads_bulk': 3600,        # 1 hour
        'update_leads_bulk': 1800,        # 30 minutes
        'delete_receipts_all': 3600,      # 1 hour
        'delete_imported_leads': 1800,    # 30 minutes
        'broadcast_whatsapp': 7200,       # 2 hours
        'enqueue_outbound_calls': 3600,   # 1 hour
        'default': 1800                   # 30 minutes
    }
    
    def __init__(self, redis_client):
        """
        Initialize BulkGate
        
        Args:
            redis_client: Redis connection instance
        """
        self.redis = redis_client
    
    def can_enqueue(
        self,
        business_id: int,
        operation_type: str,
        user_id: Optional[int] = None,
        params_hash: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if enqueue is allowed for this operation
        
        Args:
            business_id: Business ID
            operation_type: Type of operation (e.g., 'delete_leads_bulk')
            user_id: User ID (for logging)
            params_hash: Hash of operation parameters (for deduplication)
        
        Returns:
            (allowed: bool, reason: str)
        """
        # Check 1: Active job lock
        lock_key = f"bulk_gate:lock:{business_id}:{operation_type}"
        if self.redis.exists(lock_key):
            ttl = self.redis.ttl(lock_key)
            logger.warning(
                f"🚫 BULK_GATE: Active job exists "
                f"business_id={business_id} operation={operation_type} ttl={ttl}s"
            )
            return False, f"פעולה פעילה כבר רצה. נסה שוב בעוד {ttl} שניות"
        
        # Check 2: Rate limiting
        rate_limit = self.RATE_LIMITS.get(operation_type, self.RATE_LIMITS['default'])
        rate_key = f"bulk_gate:rate:{business_id}:{operation_type}"
        
        # Get current count in last minute
        now = time.time()
        one_minute_ago = now - 60
        
        # Clean old entries
        self.redis.zremrangebyscore(rate_key, 0, one_minute_ago)
        
        # Count recent enqueues
        count = self.redis.zcount(rate_key, one_minute_ago, now)
        
        if count >= rate_limit:
            logger.warning(
                f"🚫 BULK_GATE: Rate limit exceeded "
                f"business_id={business_id} operation={operation_type} "
                f"count={count}/{rate_limit}"
            )
            return False, f"חרגת ממגבלת קצב. מקסימום {rate_limit} פעולות בדקה"
        
        # Check 3: Deduplication (if params_hash provided)
        if params_hash:
            dedup_key = f"bulk_gate:dedup:{business_id}:{operation_type}:{params_hash}"
            if self.redis.exists(dedup_key):
                ttl = self.redis.ttl(dedup_key)
                logger.info(
                    f"🔁 BULK_GATE: Duplicate operation "
                    f"business_id={business_id} operation={operation_type} "
                    f"params_hash={params_hash} ttl={ttl}s"
                )
                return False, f"פעולה זהה כבר בוצעה לאחרונה"
        
        # All checks passed
        logger.info(
            f"✅ BULK_GATE: Enqueue allowed "
            f"business_id={business_id} operation={operation_type} "
            f"rate={count}/{rate_limit}"
        )
        return True, "ok"
    
    def acquire_lock(
        self,
        business_id: int,
        operation_type: str,
        job_id: Optional[int] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Acquire lock for this operation
        
        Args:
            business_id: Business ID
            operation_type: Type of operation
            job_id: BackgroundJob ID (for tracking)
            ttl: Lock TTL in seconds (uses default if not provided)
        
        Returns:
            True if lock acquired, False if already locked
        """
        lock_key = f"bulk_gate:lock:{business_id}:{operation_type}"
        lock_ttl = ttl or self.LOCK_TTL.get(operation_type, self.LOCK_TTL['default'])
        
        # Try to acquire lock (SET NX)
        lock_value = f"job_{job_id}" if job_id else "locked"
        acquired = self.redis.set(lock_key, lock_value, nx=True, ex=lock_ttl)
        
        if acquired:
            logger.info(
                f"🔒 BULK_GATE: Lock acquired "
                f"business_id={business_id} operation={operation_type} "
                f"job_id={job_id} ttl={lock_ttl}s"
            )
        else:
            logger.warning(
                f"🚫 BULK_GATE: Lock already held "
                f"business_id={business_id} operation={operation_type}"
            )
        
        return bool(acquired)
    
    def release_lock(
        self,
        business_id: int,
        operation_type: str
    ):
        """
        Release lock for this operation
        
        Args:
            business_id: Business ID
            operation_type: Type of operation
        """
        lock_key = f"bulk_gate:lock:{business_id}:{operation_type}"
        deleted = self.redis.delete(lock_key)
        
        if deleted:
            logger.info(
                f"🔓 BULK_GATE: Lock released "
                f"business_id={business_id} operation={operation_type}"
            )
        
        return deleted > 0
    
    def record_enqueue(
        self,
        business_id: int,
        operation_type: str,
        params_hash: Optional[str] = None,
        dedup_ttl: int = 600
    ):
        """
        Record that an enqueue happened (for rate limiting and deduplication)
        
        Args:
            business_id: Business ID
            operation_type: Type of operation
            params_hash: Hash of operation parameters (for deduplication)
            dedup_ttl: Deduplication TTL in seconds (default: 10 minutes)
        """
        # Record in rate limiting sorted set
        rate_key = f"bulk_gate:rate:{business_id}:{operation_type}"
        now = time.time()
        self.redis.zadd(rate_key, {str(now): now})
        self.redis.expire(rate_key, 120)  # Keep for 2 minutes
        
        # Record deduplication if params_hash provided
        if params_hash:
            dedup_key = f"bulk_gate:dedup:{business_id}:{operation_type}:{params_hash}"
            self.redis.setex(dedup_key, dedup_ttl, "1")
        
        logger.debug(
            f"📝 BULK_GATE: Enqueue recorded "
            f"business_id={business_id} operation={operation_type}"
        )


# Singleton instance (initialized on first use)
_bulk_gate_instance: Optional[BulkGate] = None


def get_bulk_gate(redis_client=None) -> Optional[BulkGate]:
    """
    Get or create BulkGate singleton instance
    
    Args:
        redis_client: Redis connection (required on first call)
    
    Returns:
        BulkGate instance or None if Redis not available
    """
    global _bulk_gate_instance
    
    if _bulk_gate_instance is None:
        if redis_client is None:
            logger.warning("BulkGate: Redis client not provided, gate disabled")
            return None
        
        _bulk_gate_instance = BulkGate(redis_client)
        logger.info("✅ BulkGate initialized")
    
    return _bulk_gate_instance
