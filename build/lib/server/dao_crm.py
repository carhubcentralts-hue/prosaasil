"""
DAO functions for unified CRM system
"""
from server.db import db
from sqlalchemy import text
import logging
from datetime import datetime

log = logging.getLogger(__name__)

def upsert_thread(business_id: int, type_: str, provider: str, peer_number: str, title: str | None = None) -> int:
    """
    Find or create a thread for unified messaging
    Returns thread_id
    """
    try:
        # First try to find existing thread
        result = db.session.execute(text("""
            SELECT id FROM threads 
            WHERE business_id = :business_id AND type = :type AND provider = :provider AND peer_number = :peer_number
            LIMIT 1
        """), {
            "business_id": business_id, 
            "type": type_, 
            "provider": provider, 
            "peer_number": peer_number
        })
        
        row = result.fetchone()
        if row:
            # Update last_message_at
            db.session.execute(text("""
                UPDATE threads SET last_message_at = CURRENT_TIMESTAMP WHERE id = :thread_id
            """), {"thread_id": row[0]})
            db.session.commit()
            return row[0]
        
        # Create new thread
        result = db.session.execute(text("""
            INSERT INTO threads (business_id, type, provider, peer_number, title, last_message_at, created_at)
            VALUES (:business_id, :type, :provider, :peer_number, :title, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
        """), {
            "business_id": business_id,
            "type": type_,
            "provider": provider,
            "peer_number": peer_number,
            "title": title or f"{provider} {peer_number}"
        })
        
        row = result.fetchone()
        if not row:
            raise Exception("Failed to create thread")
        thread_id = row[0]
        db.session.commit()
        log.info(f"Created new thread {thread_id} for {provider} {peer_number}")
        return thread_id
        
    except Exception as e:
        db.session.rollback()
        log.error(f"Error upserting thread: {e}")
        raise

def insert_message(thread_id: int, direction: str, message_type: str, content_text: str | None = None, 
                  media_url: str | None = None, provider_msg_id: str | None = None, status: str = "received") -> int:
    """
    Insert a message into the unified messaging system with idempotency protection
    Returns message_id
    """
    try:
        # Check for duplicate provider_msg_id (idempotency)
        if provider_msg_id:
            existing = db.session.execute(text("""
                SELECT id FROM messages WHERE provider_msg_id = :provider_msg_id
            """), {"provider_msg_id": provider_msg_id}).fetchone()
            
            if existing:
                log.info(f"Message {provider_msg_id} already exists (idempotency), returning existing ID {existing[0]}")
                return existing[0]
        result = db.session.execute(text("""
            INSERT INTO messages (thread_id, direction, message_type, content_text, media_url, provider_msg_id, status, created_at)
            VALUES (:thread_id, :direction, :message_type, :content_text, :media_url, :provider_msg_id, :status, CURRENT_TIMESTAMP)
            RETURNING id
        """), {
            "thread_id": thread_id,
            "direction": direction,
            "message_type": message_type,
            "content_text": content_text or "",
            "media_url": media_url or "",
            "provider_msg_id": provider_msg_id or "",
            "status": status
        })
        
        row = result.fetchone()
        if not row:
            raise Exception("Failed to create message")
        message_id = row[0]
        
        # Update thread's last_message_at
        db.session.execute(text("""
            UPDATE threads SET last_message_at = CURRENT_TIMESTAMP WHERE id = :thread_id
        """), {"thread_id": thread_id})
        
        db.session.commit()
        log.info(f"Inserted new message {message_id} to thread {thread_id} (provider_msg_id: {provider_msg_id})")
        return message_id
        
    except Exception as e:
        db.session.rollback()
        log.error(f"Error inserting message: {e}")
        raise

def get_threads(business_id: int, type_: str | None = None, limit: int = 50, offset: int = 0) -> list:
    """
    Get threads for a business with optional filtering
    """
    try:
        where_clause = "WHERE business_id = :business_id"
        params = {"business_id": business_id, "limit": limit, "offset": offset}
        
        if type_ is not None:
            where_clause += " AND type = :type_filter"
            params["type_filter"] = type_
        
        result = db.session.execute(text(f"""
            SELECT id, type, provider, peer_number, title, last_message_at, created_at
            FROM threads 
            {where_clause}
            ORDER BY last_message_at DESC
            LIMIT :limit OFFSET :offset
        """), params)
        
        return [dict(row._mapping) for row in result.fetchall()]
        
    except Exception as e:
        log.error(f"Error getting threads: {e}")
        return []

def get_thread_messages(thread_id: int, limit: int = 100, offset: int = 0) -> list:
    """
    Get messages for a specific thread
    """
    try:
        result = db.session.execute(text("""
            SELECT id, direction, message_type, content_text, media_url, provider_msg_id, status, created_at
            FROM messages 
            WHERE thread_id = :thread_id
            ORDER BY created_at ASC
            LIMIT :limit OFFSET :offset
        """), {"thread_id": thread_id, "limit": limit, "offset": offset})
        
        return [dict(row._mapping) for row in result.fetchall()]
        
    except Exception as e:
        log.error(f"Error getting thread messages: {e}")
        return []

def get_thread_by_peer(business_id: int, type_: str, peer_number: str) -> dict | None:
    """
    Get thread data by peer number for smart routing
    Returns thread data with last message info
    """
    try:
        # Get thread with last message info
        result = db.session.execute(text("""
            SELECT t.id, t.provider, t.last_message_at,
                   m.direction as last_direction, m.created_at as last_message_time
            FROM threads t
            LEFT JOIN messages m ON t.id = m.thread_id
            WHERE t.business_id = :business_id AND t.type = :type AND t.peer_number = :peer_number
            ORDER BY m.created_at DESC
            LIMIT 1
        """), {
            "business_id": business_id,
            "type": type_,
            "peer_number": peer_number
        })
        
        row = result.fetchone()
        if row:
            return {
                "thread_id": row[0],
                "last_provider": row[1],
                "last_message_at": row[2],
                "last_direction": row[3],
                "last_user_message_time": row[4] if row[3] == "in" else None
            }
        
        return None
        
    except Exception as e:
        log.error(f"Error getting thread by peer: {e}")
        return None

def get_messages_by_business(business_id: int, direction: str | None = None, status: str | None = None, page: int = 1, per_page: int = 20) -> dict:
    """
    Get messages for a business with pagination - UNIFIED VERSION
    """
    try:
        offset = (page - 1) * per_page
        where_clause = "WHERE t.business_id = :business_id"
        params = {"business_id": business_id, "limit": per_page, "offset": offset}
        
        if direction:
            where_clause += " AND m.direction = :direction"
            params["direction"] = direction
            
        if status:
            where_clause += " AND m.status = :status"
            params["status"] = status
        
        # Get messages with thread info
        result = db.session.execute(text(f"""
            SELECT m.id, m.direction, m.message_type, m.content_text, m.media_url, 
                   m.provider_msg_id, m.status, m.created_at,
                   t.provider, t.peer_number, t.business_id
            FROM messages m
            JOIN threads t ON m.thread_id = t.id
            {where_clause}
            ORDER BY m.created_at DESC
            LIMIT :limit OFFSET :offset
        """), params)
        
        messages = []
        for row in result.fetchall():
            messages.append({
                "id": row[0],
                "direction": row[1], 
                "message_type": row[2],
                "body": row[3],  # content_text -> body for compatibility
                "media_url": row[4],
                "provider_message_id": row[5], 
                "status": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
                "provider": row[8],
                "to_number": row[9],  # peer_number -> to_number for compatibility
                "business_id": row[10]
            })
        
        # Get total count for pagination
        count_params = {k: v for k, v in params.items() if k not in ["limit", "offset"]}
        count_result = db.session.execute(text(f"""
            SELECT COUNT(*)
            FROM messages m
            JOIN threads t ON m.thread_id = t.id
            {where_clause}
        """), count_params)
        
        count_row = count_result.fetchone()
        total = count_row[0] if count_row else 0
        
        return {
            "messages": messages,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        log.error(f"Error getting messages by business: {e}")
        return {"messages": [], "pagination": {"page": page, "per_page": per_page, "total": 0, "pages": 0}}