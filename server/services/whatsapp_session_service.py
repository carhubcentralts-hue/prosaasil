"""
WhatsApp Session Service - Conversation Tracking and Auto-Summary
BUILD 162: Session lifecycle management with 15-minute inactivity auto-summary

This service tracks WhatsApp conversation sessions:
1. Opens new session on first message
2. Updates last_message_at on each message
3. Closes session + generates summary after 15min inactivity
4. Links sessions to leads when available
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from server.db import db
from server.models_sql import WhatsAppConversation, WhatsAppMessage, Lead

logger = logging.getLogger(__name__)

INACTIVITY_MINUTES = 15
CHECK_INTERVAL_SECONDS = 300  # Check every 5 minutes

_session_processor_started = False
_session_processor_lock = threading.Lock()


def get_or_create_session(
    business_id: int,
    customer_wa_id: str,
    provider: str = "baileys"
) -> Tuple[WhatsAppConversation, bool]:
    """Get existing open session or create new one
    
    Session Rules (BUILD 163):
    1. Session is per-customer (customer_wa_id) + per-business
    2. Session is valid only for SAME DAY - new day = new session
    3. If 15+ minutes passed since last CUSTOMER message = close old, create new
    4. Business messages don't reset the 15-minute inactivity timer
    
    Args:
        business_id: Business ID
        customer_wa_id: Customer WhatsApp number (cleaned)
        provider: WhatsApp provider (baileys/meta)
    
    Returns:
        Tuple of (WhatsAppConversation, is_new_session)
    """
    customer_wa_id = customer_wa_id.replace("@s.whatsapp.net", "").replace("+", "").strip()
    
    # Find any open session for this customer
    session = WhatsAppConversation.query.filter_by(
        business_id=business_id,
        customer_wa_id=customer_wa_id,
        is_open=True
    ).first()
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if session:
        # 🔥 BUILD 163: Check 1 - Is session from TODAY?
        session_day = session.started_at.replace(hour=0, minute=0, second=0, microsecond=0) if session.started_at else None
        if session_day and session_day < today_start:
            # Session is from a previous day - close it and create new
            session.is_open = False
            db.session.commit()
            logger.info(f"[WA-SESSION] Closed old-day session id={session.id} (started {session.started_at.date()})")
            session = None
        
        # 🔥 BUILD 163: Check 2 - Has 15+ minutes passed since last CUSTOMER message?
        elif session.last_customer_message_at:
            cutoff = now - timedelta(minutes=INACTIVITY_MINUTES)
            if session.last_customer_message_at < cutoff:
                # Customer inactive for 15+ min - close session, background will summarize
                session.is_open = False
                db.session.commit()
                logger.info(f"[WA-SESSION] Closed stale session id={session.id} (customer inactive > {INACTIVITY_MINUTES}min)")
                session = None
    
    if session:
        return session, False
    
    lead_id = None
    lead = Lead.query.filter_by(
        tenant_id=business_id,
        phone_e164=customer_wa_id
    ).first()
    
    if not lead:
        normalized = f"+{customer_wa_id}" if not customer_wa_id.startswith("+") else customer_wa_id
        lead = Lead.query.filter_by(
            tenant_id=business_id,
            phone_e164=normalized
        ).first()
    
    if lead:
        lead_id = lead.id
    
    new_session = WhatsAppConversation(
        business_id=business_id,
        customer_number=customer_wa_id,  # ✅ BUILD 170.1: Required field!
        provider=provider,
        customer_wa_id=customer_wa_id,
        lead_id=lead_id,
        started_at=datetime.utcnow(),
        last_message_at=datetime.utcnow(),
        last_customer_message_at=datetime.utcnow(),
        is_open=True,
        summary_created=False
    )
    
    db.session.add(new_session)
    db.session.commit()
    
    logger.info(f"[WA-SESSION] Created new session id={new_session.id} for customer={customer_wa_id[:8]}... lead_id={lead_id}")
    
    return new_session, True


def update_session_activity(
    business_id: int,
    customer_wa_id: str,
    direction: str = "in",
    provider: str = "baileys"
) -> Optional[WhatsAppConversation]:
    """Update session's last_message_at timestamp
    
    Args:
        business_id: Business ID
        customer_wa_id: Customer WhatsApp number
        direction: "in" for customer message, "out" for business message
        provider: WhatsApp provider
    
    Returns:
        Updated session or None
    """
    try:
        session, is_new = get_or_create_session(business_id, customer_wa_id, provider)
        
        now = datetime.utcnow()
        session.last_message_at = now
        
        if direction == "in":
            session.last_customer_message_at = now
        
        session.updated_at = now
        
        db.session.commit()
        
        logger.debug(f"[WA-SESSION] Updated session id={session.id} last_message_at={now} direction={direction}")
        
        return session
    except Exception as e:
        # ✅ BUILD 170.1: Rollback on error to prevent session poisoning
        logger.error(f"[WA-SESSION] update_session_activity failed: {e}")
        try:
            db.session.rollback()
        except:
            pass
        raise  # Re-raise so caller knows it failed


def close_session(session_id: int, summary: Optional[str] = None, mark_processed: bool = True) -> bool:
    """Close a session and optionally set summary
    
    BUILD 163 FIX: Always mark summary_created=True to prevent infinite reprocessing
    of sessions that have too few messages for summary generation.
    
    Args:
        session_id: Session ID
        summary: Optional AI-generated summary
        mark_processed: If True, always mark summary_created=True (default)
    
    Returns:
        True if closed successfully
    """
    session = WhatsAppConversation.query.get(session_id)
    if not session:
        logger.warning(f"[WA-SESSION] Session not found: {session_id}")
        return False
    
    session.is_open = False
    session.updated_at = datetime.utcnow()
    
    # 🔥 BUILD 163: Always mark as processed to avoid infinite reprocessing
    if mark_processed:
        session.summary_created = True
    
    if summary:
        session.summary = summary
        
        if session.lead_id:
            lead = Lead.query.get(session.lead_id)
            if lead:
                lead.whatsapp_last_summary = summary
                lead.whatsapp_last_summary_at = datetime.utcnow()
                logger.info(f"[WA-SESSION] Updated lead {lead.id} with session summary")
    else:
        # No summary (too few messages) - log it but still mark as processed
        logger.info(f"[WA-SESSION] Session {session_id} closed without summary (not enough messages)")
    
    db.session.commit()
    
    logger.info(f"[WA-SESSION] Closed session id={session_id} with_summary={bool(summary)} processed={mark_processed}")
    
    return True


def get_active_chats_count(business_id: int) -> int:
    """Get count of active (open) WhatsApp conversations
    
    Args:
        business_id: Business ID
    
    Returns:
        Number of open sessions
    """
    count = WhatsAppConversation.query.filter_by(
        business_id=business_id,
        is_open=True
    ).count()
    
    return count


def get_active_chats(business_id: int, limit: int = 50) -> list:
    """Get list of active WhatsApp conversations
    
    Args:
        business_id: Business ID
        limit: Max number of chats to return
    
    Returns:
        List of active session dicts
    """
    sessions = WhatsAppConversation.query.filter_by(
        business_id=business_id,
        is_open=True
    ).order_by(
        WhatsAppConversation.last_message_at.desc()
    ).limit(limit).all()
    
    result = []
    for s in sessions:
        lead_name = None
        if s.lead_id:
            lead = Lead.query.get(s.lead_id)
            if lead:
                lead_name = lead.full_name
        
        result.append({
            "id": s.id,
            "customer_wa_id": s.customer_wa_id,
            "lead_id": s.lead_id,
            "lead_name": lead_name,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "last_message_at": s.last_message_at.isoformat() if s.last_message_at else None,
            "provider": s.provider
        })
    
    return result


def get_customer_sessions(business_id: int, customer_wa_id: str, limit: int = 20) -> list:
    """Get all sessions for a specific customer (BUILD 163)
    
    Returns session history for a customer, ordered by most recent first.
    Each session has its summary (if generated).
    
    Args:
        business_id: Business ID
        customer_wa_id: Customer WhatsApp number
        limit: Max sessions to return
    
    Returns:
        List of session dicts with summaries
    """
    customer_wa_id = customer_wa_id.replace("@s.whatsapp.net", "").replace("+", "").strip()
    
    sessions = WhatsAppConversation.query.filter_by(
        business_id=business_id,
        customer_wa_id=customer_wa_id
    ).order_by(
        WhatsAppConversation.started_at.desc()
    ).limit(limit).all()
    
    result = []
    for s in sessions:
        result.append({
            "id": s.id,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "last_message_at": s.last_message_at.isoformat() if s.last_message_at else None,
            "is_open": s.is_open,
            "summary": s.summary,
            "summary_created": s.summary_created
        })
    
    return result


def get_stale_sessions(minutes: int = INACTIVITY_MINUTES) -> list:
    """Get sessions that need summary generation
    
    BUILD 163: Find sessions that need AI summary:
    1. OPEN sessions where customer inactive > 15 min (still needs closing + summary)
    2. CLOSED sessions without summary (closed by new session creation, needs summary)
    
    Args:
        minutes: Inactivity threshold in minutes
    
    Returns:
        List of WhatsAppConversation objects that need summary
    """
    from sqlalchemy import or_
    
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    
    # Find sessions needing summary:
    # 1. Open + customer inactive > 15 min + no summary yet
    # 2. Closed + no summary yet (was closed by new session creation)
    stale = WhatsAppConversation.query.filter(
        WhatsAppConversation.summary_created == False,
        or_(
            # Case 1: Open but stale
            (WhatsAppConversation.is_open == True) & 
            (WhatsAppConversation.last_customer_message_at < cutoff),
            # Case 2: Closed without summary (closed by new session, needs summary now)
            (WhatsAppConversation.is_open == False)
        )
    ).all()
    
    return stale


def get_session_messages(session: WhatsAppConversation) -> list:
    """Get all messages for a session (for summary generation)
    
    🔥 FIX: Query with flexible phone number matching to handle different formats
    Also adds upper bound (last_message_at) to prevent including messages from after session ended
    
    Args:
        session: WhatsAppConversation object
    
    Returns:
        List of message dicts with direction and body
    """
    from sqlalchemy import or_, func
    
    if not session.started_at:
        logger.warning(f"[WA-SESSION] No started_at for session {session.id}")
        return []
    
    # 🔥 Normalize customer phone for flexible matching
    customer_phone = session.customer_wa_id or ""
    customer_phone_clean = customer_phone.replace("@s.whatsapp.net", "").replace("+", "").strip()
    
    # Build list of possible phone formats to match (EXACT matches only - no LIKE for security!)
    phone_variants = [
        customer_phone_clean,                    # 972501234567
        f"+{customer_phone_clean}",              # +972501234567
        f"{customer_phone_clean}@s.whatsapp.net" # 972501234567@s.whatsapp.net
    ]
    
    # 🔥 Add upper bound: only messages from session.started_at to session.last_message_at
    # This prevents including messages from AFTER the session was considered ended
    end_time = session.last_message_at or session.updated_at or datetime.utcnow()
    
    # Query with EXACT phone matching only (no LIKE - prevents cross-customer data leak!)
    messages = WhatsAppMessage.query.filter(
        WhatsAppMessage.business_id == session.business_id,
        or_(
            WhatsAppMessage.to_number == phone_variants[0],
            WhatsAppMessage.to_number == phone_variants[1],
            WhatsAppMessage.to_number == phone_variants[2]
        ),
        WhatsAppMessage.created_at >= session.started_at,
        WhatsAppMessage.created_at <= end_time  # 🔥 Upper bound!
    ).order_by(WhatsAppMessage.created_at.asc()).all()
    
    # 🔥 DEBUG: Log message count for troubleshooting
    logger.info(f"[WA-SESSION] Found {len(messages)} messages for session {session.id}")
    logger.info(f"   customer={customer_phone_clean[:8]}..., from={session.started_at}, to={end_time}")
    
    result = []
    for m in messages:
        result.append({
            "direction": m.direction or "in",
            "body": m.body or "",
            "timestamp": m.created_at.isoformat() if m.created_at else None
        })
    
    return result


def generate_session_summary(session: WhatsAppConversation) -> Optional[str]:
    """Generate AI summary for a session
    
    Args:
        session: WhatsAppConversation object
    
    Returns:
        Summary text or None if failed
    """
    import os
    
    messages = get_session_messages(session)
    if not messages or len(messages) < 2:
        logger.info(f"[WA-SESSION] Not enough messages for summary (session={session.id})")
        return None
    
    conversation_text = ""
    for m in messages:
        speaker = "לקוח" if m["direction"] == "in" else "עסק"
        conversation_text += f"{speaker}: {m['body']}\n"
    
    prompt = f"""סכם את השיחה הבאה ב-WhatsApp בעברית. הסיכום צריך להיות קצר (2-3 משפטים) וממוקד בנקודות העיקריות:
- מה הלקוח רצה
- מה סוכם/הוחלט
- האם יש פעולות המשך נדרשות

שיחה:
{conversation_text}

סיכום:"""
    
    try:
        import openai
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("[WA-SESSION] No OpenAI API key for summary generation")
            return None
        
        client = openai.OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "אתה עוזר שמסכם שיחות WhatsApp בעברית. הסיכומים שלך קצרים וממוקדים."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        if not content:
            logger.warning(f"[WA-SESSION] Empty response from OpenAI for session {session.id}")
            return None
        summary = content.strip()
        logger.info(f"[WA-SESSION] Generated summary for session {session.id}: {summary[:50]}...")
        
        return summary
        
    except Exception as e:
        logger.error(f"[WA-SESSION] Failed to generate summary: {e}")
        return None


def process_stale_sessions():
    """Background job: Find and close stale sessions with AI summaries
    
    This should be called periodically (e.g., every 5 minutes) to:
    1. Find sessions inactive for 15+ minutes
    2. Generate AI summaries
    3. Close sessions and update leads
    """
    stale = get_stale_sessions()
    
    if not stale:
        logger.debug("[WA-SESSION] No stale sessions to process")
        return 0
    
    logger.info(f"[WA-SESSION] Processing {len(stale)} stale sessions")
    
    processed = 0
    for session in stale:
        try:
            summary = generate_session_summary(session)
            
            close_session(session.id, summary=summary)
            processed += 1
            
        except Exception as e:
            logger.error(f"[WA-SESSION] Error processing session {session.id}: {e}")
    
    logger.info(f"[WA-SESSION] Processed {processed} stale sessions")
    
    return processed


def _session_processor_loop():
    """Background thread loop that processes stale sessions every 5 minutes"""
    logger.info("[WA-SESSION] Background processor thread started")
    print("[WA-SESSION] 📱 Background processor thread started - checking every 5 minutes")
    
    # Wait 60 seconds after startup before first check
    time.sleep(60)
    
    iteration = 0
    while True:
        iteration += 1
        try:
            from server.app_factory import get_process_app
            app = get_process_app()
            
            with app.app_context():
                # 🔥 DEBUG: Log every check for troubleshooting
                stale_count = len(get_stale_sessions())
                print(f"[WA-SESSION] 📱 Check #{iteration}: Found {stale_count} stale sessions to process")
                logger.info(f"[WA-SESSION] Check #{iteration}: Found {stale_count} stale sessions")
                
                processed = process_stale_sessions()
                if processed > 0:
                    print(f"[WA-SESSION] ✅ Processed {processed} stale sessions with AI summaries")
                    logger.info(f"[WA-SESSION] Background job: processed {processed} sessions")
        except Exception as e:
            print(f"[WA-SESSION] ❌ Background processor error: {e}")
            logger.error(f"[WA-SESSION] Background processor error: {e}")
            import traceback
            traceback.print_exc()
        
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_session_processor():
    """Start the background session processor thread
    
    This should be called once when the application starts.
    It will start a daemon thread that processes stale sessions
    every 5 minutes.
    """
    global _session_processor_started
    
    with _session_processor_lock:
        if _session_processor_started:
            logger.info("[WA-SESSION] Background processor already started")
            return False
        
        processor_thread = threading.Thread(
            target=_session_processor_loop,
            daemon=True,
            name="WhatsAppSessionProcessor"
        )
        processor_thread.start()
        
        _session_processor_started = True
        logger.info("[WA-SESSION] Background processor thread started successfully")
        
        return True


def migrate_existing_messages_to_sessions() -> dict:
    """One-time migration: Create sessions from existing WhatsApp messages
    
    This analyzes all existing messages and creates closed sessions with summaries
    for each unique customer conversation. Sessions are marked as already summarized
    so they won't be processed again.
    
    Returns:
        Dict with migration statistics
    """
    from sqlalchemy import func, distinct
    
    logger.info("[WA-SESSION] Starting migration of existing messages to sessions...")
    
    unique_conversations = db.session.query(
        WhatsAppMessage.business_id,
        WhatsAppMessage.to_number
    ).filter(
        WhatsAppMessage.to_number.isnot(None)
    ).distinct().all()
    
    logger.info(f"[WA-SESSION] Found {len(unique_conversations)} unique conversations to process")
    
    created = 0
    skipped = 0
    errors = 0
    
    for business_id, customer_phone in unique_conversations:
        if not customer_phone:
            continue
            
        customer_phone_clean = customer_phone.replace("@s.whatsapp.net", "").replace("+", "").strip()
        
        existing = WhatsAppConversation.query.filter_by(
            business_id=business_id,
            customer_wa_id=customer_phone_clean
        ).first()
        
        if existing:
            skipped += 1
            continue
        
        try:
            messages = WhatsAppMessage.query.filter(
                WhatsAppMessage.business_id == business_id,
                WhatsAppMessage.to_number == customer_phone
            ).order_by(WhatsAppMessage.created_at.asc()).all()
            
            if not messages:
                continue
            
            first_msg = messages[0]
            last_msg = messages[-1]
            
            lead_id = None
            lead = Lead.query.filter_by(
                tenant_id=business_id,
                phone_e164=customer_phone_clean
            ).first()
            
            if not lead:
                normalized = f"+{customer_phone_clean}" if not customer_phone_clean.startswith("+") else customer_phone_clean
                lead = Lead.query.filter_by(
                    tenant_id=business_id,
                    phone_e164=normalized
                ).first()
            
            if lead:
                lead_id = lead.id
            
            new_session = WhatsAppConversation(
                business_id=business_id,
                provider="baileys",
                customer_wa_id=customer_phone_clean,
                lead_id=lead_id,
                started_at=first_msg.created_at,
                last_message_at=last_msg.created_at,
                last_customer_message_at=last_msg.created_at,
                is_open=False,
                summary_created=False
            )
            
            db.session.add(new_session)
            db.session.commit()
            created += 1
            
            logger.info(f"[WA-SESSION] Created session for customer={customer_phone_clean[:8]}... (business={business_id})")
            
        except Exception as e:
            errors += 1
            logger.error(f"[WA-SESSION] Error creating session for {customer_phone_clean}: {e}")
            db.session.rollback()
    
    result = {
        "total_conversations": len(unique_conversations),
        "sessions_created": created,
        "sessions_skipped": skipped,
        "errors": errors
    }
    
    logger.info(f"[WA-SESSION] Migration complete: {result}")
    
    return result
