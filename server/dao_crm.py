"""
DAO functions for unified CRM system
"""
from server.db import db
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)

def upsert_thread(business_id: int, type_: str, provider: str, peer_number: str, title: str = None) -> int:
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
        
        thread_id = result.fetchone()[0]
        db.session.commit()
        log.info(f"Created new thread {thread_id} for {provider} {peer_number}")
        return thread_id
        
    except Exception as e:
        db.session.rollback()
        log.error(f"Error upserting thread: {e}")
        raise

def insert_message(thread_id: int, direction: str, message_type: str, content_text: str = None, 
                  media_url: str = None, provider_msg_id: str = None, status: str = "received") -> int:
    """
    Insert a message into the unified messaging system
    Returns message_id
    """
    try:
        result = db.session.execute(text("""
            INSERT INTO messages (thread_id, direction, message_type, content_text, media_url, provider_msg_id, status, created_at)
            VALUES (:thread_id, :direction, :message_type, :content_text, :media_url, :provider_msg_id, :status, CURRENT_TIMESTAMP)
            RETURNING id
        """), {
            "thread_id": thread_id,
            "direction": direction,
            "message_type": message_type,
            "content_text": content_text,
            "media_url": media_url,
            "provider_msg_id": provider_msg_id,
            "status": status
        })
        
        message_id = result.fetchone()[0]
        
        # Update thread's last_message_at
        db.session.execute(text("""
            UPDATE threads SET last_message_at = CURRENT_TIMESTAMP WHERE id = :thread_id
        """), {"thread_id": thread_id})
        
        db.session.commit()
        log.info(f"Inserted message {message_id} to thread {thread_id}")
        return message_id
        
    except Exception as e:
        db.session.rollback()
        log.error(f"Error inserting message: {e}")
        raise

def get_threads(business_id: int, type_: str = None, limit: int = 50, offset: int = 0) -> list:
    """
    Get threads for a business with optional filtering
    """
    try:
        where_clause = "WHERE business_id = :business_id"
        params = {"business_id": business_id, "limit": limit, "offset": offset}
        
        if type_:
            where_clause += " AND type = :type"
            params["type"] = type_
        
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