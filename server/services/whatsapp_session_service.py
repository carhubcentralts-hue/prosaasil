"""
WhatsApp Session Service - Conversation Tracking and Auto-Summary
BUILD 162: Session lifecycle management with 15-minute inactivity auto-summary

This service tracks WhatsApp conversation sessions:
1. Opens new session on first message
2. Updates last_message_at on each message
3. Closes session + generates summary after 15min inactivity
4. Links sessions to leads when available

DB RESILIENCE: Background loops handle DB outages gracefully with exponential backoff
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from server.db import db
from server.models_sql import WhatsAppConversation, WhatsAppMessage, Lead
from sqlalchemy.exc import OperationalError, DisconnectionError
import psycopg2

logger = logging.getLogger(__name__)

INACTIVITY_MINUTES = 5  # 🔥 FIX: Changed from 15 to 5 minutes for faster summaries
CHECK_INTERVAL_SECONDS = 300  # Check every 5 minutes

_session_processor_started = False
_session_processor_lock = threading.Lock()


def get_or_create_session(
    business_id: int,
    customer_wa_id: str,
    provider: str = "baileys",
    lead_id: Optional[int] = None,
    phone_e164: Optional[str] = None
) -> Tuple[WhatsAppConversation, bool]:
    """Get existing open session or create new one using canonical key
    
    Session Rules (BUILD 138 - Canonical Key / BUILD 163 - Session Lifecycle):
    1. Session is uniquely identified by canonical_key = (business_id, lead_id) OR (business_id, phone_e164)
    2. Session is valid only for SAME DAY - new day = new session
    3. If 5+ minutes passed since last CUSTOMER message = close old, create new
    4. Business messages don't reset the 5-minute inactivity timer
    
    Args:
        business_id: Business ID
        customer_wa_id: Customer WhatsApp number (cleaned) - used for legacy lookups
        provider: WhatsApp provider (baileys/meta)
        lead_id: Lead ID if customer is identified (preferred for canonical key)
        phone_e164: Normalized E.164 phone number (fallback for canonical key)
    
    Returns:
        Tuple of (WhatsAppConversation, is_new_session)
    """
    from server.utils.whatsapp_utils import get_canonical_conversation_key
    
    customer_wa_id = customer_wa_id.replace("@s.whatsapp.net", "").replace("+", "").strip()
    
    # 🔥 BUILD 138: Generate canonical key
    canonical_key = None
    try:
        # Ensure phone_e164 is properly formatted
        if phone_e164 and not phone_e164.startswith('+'):
            phone_e164_normalized = f"+{phone_e164}"
        else:
            phone_e164_normalized = phone_e164
            
        canonical_key = get_canonical_conversation_key(
            business_id=business_id,
            lead_id=lead_id,
            phone_e164=phone_e164_normalized
        )
        logger.info(f"[WA-SESSION] Generated canonical_key: {canonical_key}")
    except Exception as e:
        logger.warning(f"[WA-SESSION] Could not generate canonical_key: {e}")
        # Fallback to legacy behavior if canonical key generation fails
    
    # Find existing session
    session = None
    
    # 🔥 BUILD 138: Try canonical key first (preferred)
    if canonical_key:
        session = WhatsAppConversation.query.filter_by(
            business_id=business_id,
            canonical_key=canonical_key,
            is_open=True
        ).first()
        
        if session:
            logger.info(f"[WA-SESSION] Found session by canonical_key: session_id={session.id}")
    
    # Fallback: Try legacy customer_wa_id lookup
    if not session:
        session = WhatsAppConversation.query.filter_by(
            business_id=business_id,
            customer_wa_id=customer_wa_id,
            is_open=True
        ).first()
        
        if session:
            logger.info(f"[WA-SESSION] Found session by customer_wa_id (legacy): session_id={session.id}")
            # 🔥 BUILD 138: Update legacy session with canonical_key
            if canonical_key and not session.canonical_key:
                session.canonical_key = canonical_key
                logger.info(f"[WA-SESSION] Updated legacy session with canonical_key: {canonical_key}")
    
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
        
        # 🔥 BUILD 163: Check 2 - Has 5+ minutes passed since last CUSTOMER message?
        elif session.last_customer_message_at:
            cutoff = now - timedelta(minutes=INACTIVITY_MINUTES)
            if session.last_customer_message_at < cutoff:
                # Customer inactive for 5+ min - close session, background will summarize
                session.is_open = False
                db.session.commit()
                logger.info(f"[WA-SESSION] Closed stale session id={session.id} (customer inactive > {INACTIVITY_MINUTES}min)")
                session = None
        
        # 🔥 BUILD 138: Update lead_id if provided and not set
        if session and lead_id and not session.lead_id:
            session.lead_id = lead_id
            logger.info(f"[WA-SESSION] Updated session {session.id} with lead_id={lead_id}")
    
    if session:
        return session, False
    
    # 🔥 BUILD 138: Try to find lead if not provided
    if not lead_id:
        lead = Lead.query.filter_by(
            tenant_id=business_id,
            phone_e164=phone_e164 or (f"+{customer_wa_id}" if customer_wa_id else None)
        ).first()
        
        if not lead and customer_wa_id:
            normalized = f"+{customer_wa_id}" if not customer_wa_id.startswith("+") else customer_wa_id
            lead = Lead.query.filter_by(
                tenant_id=business_id,
                phone_e164=normalized
            ).first()
        
        if lead:
            lead_id = lead.id
            # Recalculate canonical_key with lead_id
            try:
                canonical_key = get_canonical_conversation_key(
                    business_id=business_id,
                    lead_id=lead_id,
                    phone_e164=phone_e164_normalized
                )
                logger.info(f"[WA-SESSION] Recalculated canonical_key with lead_id: {canonical_key}")
            except Exception as e:
                logger.warning(f"[WA-SESSION] Could not recalculate canonical_key: {e}")
    
    # 🔥 UPSERT: Create new session with ON CONFLICT handling to prevent UniqueViolation
    # Use PostgreSQL INSERT ... ON CONFLICT DO UPDATE for atomic operation
    from sqlalchemy.dialects.postgresql import insert
    from sqlalchemy import select
    
    now = datetime.utcnow()
    
    # Try UPSERT if canonical_key is available
    if canonical_key:
        try:
            # Prepare insert statement
            stmt = insert(WhatsAppConversation).values(
                business_id=business_id,
                customer_number=customer_wa_id,
                provider=provider,
                customer_wa_id=customer_wa_id,
                lead_id=lead_id,
                canonical_key=canonical_key,
                started_at=now,
                last_message_at=now,
                last_customer_message_at=now,
                is_open=True,
                summary_created=False,
                created_at=now,
                updated_at=now
            )
            
            # On conflict, update timestamps and reopen if closed
            from sqlalchemy import func, case
            
            stmt = stmt.on_conflict_do_update(
                index_elements=['business_id', 'canonical_key'],
                set_={
                    'last_message_at': now,
                    'last_customer_message_at': now,
                    'is_open': True,
                    'updated_at': now,
                    # Update lead_id: use new value if NOT NULL, otherwise keep existing
                    # Lead_id is semi-mutable: it can be set once (NULL → value) but not changed afterward
                    # This allows linking conversations to leads after initial creation
                    # while customer_wa_id and provider are fully immutable (part of identity)
                    'lead_id': case(
                        (stmt.excluded.lead_id.isnot(None), stmt.excluded.lead_id),
                        else_=WhatsAppConversation.lead_id
                    )
                }
            ).returning(
                WhatsAppConversation.id, 
                WhatsAppConversation.created_at,
                WhatsAppConversation.updated_at
            )
            
            result = db.session.execute(stmt)
            db.session.commit()
            
            # Fetch the conversation that was inserted or updated
            row = result.one()
            conv_id = row[0]
            created_at = row[1]
            updated_at = row[2]
            session = WhatsAppConversation.query.get(conv_id)
            
            # Determine if this was a new INSERT or an UPDATE:
            # For new records: created_at == updated_at (both set to same value on INSERT)
            # For updates: updated_at was just set to now, but created_at is older
            # Allow 1 second tolerance for timestamp precision differences
            from datetime import timedelta
            is_new = abs((updated_at - created_at).total_seconds()) < 1.0
            
            logger.info(f"[WA-SESSION] ✅ UPSERT completed: session_id={session.id} canonical_key={canonical_key} lead_id={lead_id} business_id={business_id} is_new={is_new}")
            
            return session, is_new
            
        except Exception as upsert_err:
            logger.error(f"[WA-SESSION] ⚠️ UPSERT failed, falling back to SELECT: {upsert_err}")
            # 🔥 FIX: Rollback and close the broken session to prevent "cursor already closed"
            try:
                db.session.rollback()
                db.session.close()
            except Exception as rollback_err:
                logger.error(f"[WA-SESSION] Rollback/close failed: {rollback_err}")
            
            # 🔥 FIX: Remove the broken session and let SQLAlchemy create a new one
            # This prevents "cursor already closed" errors on subsequent queries
            db.session.remove()
            
            # Fallback: Try to fetch existing conversation with fresh session
            if canonical_key:
                session = WhatsAppConversation.query.filter_by(
                    business_id=business_id,
                    canonical_key=canonical_key
                ).first()
                
                if session:
                    # Update timestamps manually
                    session.last_message_at = now
                    session.last_customer_message_at = now
                    session.is_open = True
                    session.updated_at = now
                    if lead_id and not session.lead_id:
                        session.lead_id = lead_id
                    db.session.commit()
                    logger.info(f"[WA-SESSION] ✅ Fallback update succeeded: session_id={session.id}")
                    return session, False
    
    # Final fallback: Original INSERT logic (without canonical_key or after UPSERT failed)
    # This should rarely happen in production
    new_session = WhatsAppConversation(
        business_id=business_id,
        customer_number=customer_wa_id,
        provider=provider,
        customer_wa_id=customer_wa_id,
        lead_id=lead_id,
        canonical_key=canonical_key,
        started_at=now,
        last_message_at=now,
        last_customer_message_at=now,
        is_open=True,
        summary_created=False
    )
    
    try:
        db.session.add(new_session)
        db.session.commit()
        logger.info(f"[WA-SESSION] ✨ Created NEW session id={new_session.id} canonical_key={canonical_key} lead_id={lead_id} business_id={business_id}")
        return new_session, True
    except Exception as insert_err:
        # Last resort: rollback and try to fetch existing
        logger.error(f"[WA-SESSION] ❌ Final INSERT failed: {insert_err}")
        # 🔥 FIX: Clean up broken session to prevent "cursor already closed"
        try:
            db.session.rollback()
            db.session.close()
        except Exception as rollback_err:
            logger.error(f"[WA-SESSION] Final rollback/close failed: {rollback_err}")
        
        # 🔥 FIX: Remove broken session and use fresh one
        db.session.remove()
        
        if canonical_key:
            session = WhatsAppConversation.query.filter_by(
                business_id=business_id,
                canonical_key=canonical_key
            ).first()
            if session:
                logger.info(f"[WA-SESSION] ✅ Recovered existing session: session_id={session.id}")
                return session, False
        
        # If we still can't get a session, re-raise the error
        raise


def update_session_activity(
    business_id: int,
    customer_wa_id: str,
    direction: str = "in",
    provider: str = "baileys",
    lead_id: Optional[int] = None,
    phone_e164: Optional[str] = None
) -> Optional[WhatsAppConversation]:
    """Update session's last_message_at timestamp
    
    Args:
        business_id: Business ID
        customer_wa_id: Customer WhatsApp number
        direction: "in" for customer message, "out" for business message
        provider: WhatsApp provider
        lead_id: Optional lead ID to link session to lead
        phone_e164: Optional normalized E.164 phone for canonical key
    
    Returns:
        Updated session or None
    """
    try:
        # 🔥 BUILD 138: Pass lead_id and phone_e164 to get_or_create_session
        session, is_new = get_or_create_session(
            business_id, 
            customer_wa_id, 
            provider,
            lead_id=lead_id,
            phone_e164=phone_e164
        )
        
        now = datetime.utcnow()
        session.last_message_at = now
        
        if direction == "in":
            session.last_customer_message_at = now
        
        # 🔥 FIX: Update lead_id if provided
        if lead_id and not session.lead_id:
            session.lead_id = lead_id
            logger.info(f"[WA-SESSION] 🔗 Linked session {session.id} to lead {lead_id}")
        
        session.updated_at = now
        
        db.session.commit()
        
        logger.info(f"[WA-SESSION] ✅ Updated session id={session.id} last_message_at={now} direction={direction} new={is_new} lead_id={session.lead_id}")
        
        return session
    except Exception as e:
        # ✅ BUILD 170.1: Rollback on error to prevent session poisoning
        logger.error(f"[WA-SESSION] ❌ update_session_activity FAILED: {e}")
        logger.error(f"[WA-SESSION] ❌ Context: business_id={business_id}, customer_wa_id={customer_wa_id}, direction={direction}")
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
                # 🔥 LOG: Detailed summary creation
                logger.info(f"[WA-SUMMARY] 📝 Creating summary for lead {lead.id}:")
                logger.info(f"   • Lead Name: {lead.full_name or 'N/A'}")
                logger.info(f"   • Phone: {lead.phone_e164 or lead.mobile_phone or 'N/A'}")
                logger.info(f"   • Current Status: {lead.status or 'N/A'}")
                logger.info(f"   • Summary: {summary[:100]}...")
                
                # Update legacy WhatsApp-specific fields
                lead.whatsapp_last_summary = summary
                lead.whatsapp_last_summary_at = datetime.utcnow()
                
                # 🆕 UPDATE UNIFIED CUSTOMER MEMORY FIELDS
                # These fields provide a single source of truth across all channels
                lead.last_summary = summary  # Short summary of last interaction
                lead.summary_updated_at = datetime.utcnow()
                lead.last_interaction_at = session.last_message_at or datetime.utcnow()
                lead.last_channel = 'whatsapp'
                
                logger.info(f"[WA-SUMMARY] ✅ Updated unified customer memory for lead {lead.id}")
                
                # 🔥 NEW: Create LeadNote for AI context (single source of truth)
                try:
                    from server.models_sql import LeadNote
                    
                    # Create note with customer_service_ai type so unified context picks it up
                    note = LeadNote(
                        lead_id=lead.id,
                        tenant_id=session.business_id,
                        note_type='customer_service_ai',  # 🔥 CRITICAL: This makes it visible to AI
                        content=f"סיכום שיחת WhatsApp:\n{summary}",
                        created_at=datetime.utcnow()
                    )
                    db.session.add(note)
                    logger.info(f"[WA-SUMMARY] ✅ Created LeadNote (customer_service_ai) for lead {lead.id}")
                except Exception as note_err:
                    logger.error(f"[WA-SUMMARY] ❌ Failed to create LeadNote: {note_err}", exc_info=True)
                
                # 🔥 SSOT: Trigger auto-status update from WhatsApp summary using central service
                # This ensures all WhatsApp summaries go through the same status update pipeline
                try:
                    from server.services.lead_status_update_service import get_status_update_service
                    
                    logger.info(f"[WA-STATUS] 🔍 Processing status recommendation for lead {lead.id}")
                    logger.info(f"[WA-STATUS]    - Current status: {lead.status}")
                    logger.info(f"[WA-STATUS]    - Summary: {summary[:150]}...")
                    
                    # Use central SSOT service for status updates
                    status_service = get_status_update_service()
                    
                    # Generate unique source_event_id for idempotency
                    # Use canonical_key + session_id for uniqueness
                    source_event_id = f"wa_session_{session.id}_{session.canonical_key or session.customer_wa_id}"
                    
                    success, message = status_service.apply_from_recommendation(
                        business_id=session.business_id,
                        lead_id=lead.id,
                        summary_text=summary,
                        source='whatsapp_summary',
                        source_event_id=source_event_id,
                        confidence=0.8  # AI-generated from summary
                    )
                    
                    if success:
                        logger.info(f"[WA-STATUS] ✅ {message}")
                    else:
                        logger.info(f"[WA-STATUS] ℹ️ {message}")
                        
                except Exception as e:
                    logger.error(f"[WA-STATUS] ❌ Error updating status from WhatsApp summary: {e}", exc_info=True)
                    # Don't fail the whole summary creation if status update fails
                
                # Try to extract memory patches from conversation
                try:
                    messages = get_session_messages(session)
                    logger.info(f"[WA-MEMORY] 🔍 Extracting memory patches from {len(messages)} messages")
                    
                    memory_patch = extract_memory_patch_from_messages(messages, lead)
                    if memory_patch:
                        logger.info(f"[WA-MEMORY] 📦 Extracted memory patch with {len(memory_patch)} fields: {list(memory_patch.keys())}")
                        
                        # Merge memory_patch into customer_profile_json
                        if not lead.customer_profile_json:
                            lead.customer_profile_json = {}
                        lead.customer_profile_json = merge_customer_profile(
                            lead.customer_profile_json, 
                            memory_patch
                        )
                        logger.info(f"[WA-MEMORY] ✅ Updated customer profile for lead {lead.id} - total fields: {len(lead.customer_profile_json)}")
                    else:
                        logger.info(f"[WA-MEMORY] ℹ️ No memory patches extracted from conversation")
                except Exception as e:
                    logger.warning(f"[WA-MEMORY] ⚠️ Could not extract memory patch: {e}", exc_info=True)
                
                logger.info(f"[WA-SESSION] Updated lead {lead.id} with unified customer memory")
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
        List of active session dicts with unread status
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
        
        # Calculate unread status
        # Unread if: last_customer_message_at > last_read_at (or last_read_at is None)
        is_unread = False
        if s.last_customer_message_at:
            if s.last_read_at is None:
                is_unread = True
            else:
                is_unread = s.last_customer_message_at > s.last_read_at
        
        result.append({
            "id": s.id,
            "customer_wa_id": s.customer_wa_id,
            "lead_id": s.lead_id,
            "lead_name": lead_name,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "last_message_at": s.last_message_at.isoformat() if s.last_message_at else None,
            "last_customer_message_at": s.last_customer_message_at.isoformat() if s.last_customer_message_at else None,
            "last_read_at": s.last_read_at.isoformat() if s.last_read_at else None,
            "is_unread": is_unread,
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
    1. OPEN sessions where customer inactive > 5 min (still needs closing + summary)
    2. CLOSED sessions without summary (closed by new session creation, needs summary)
    
    Args:
        minutes: Inactivity threshold in minutes
    
    Returns:
        List of WhatsAppConversation objects that need summary
    """
    from sqlalchemy import or_
    
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    
    logger.info(f"[WA-SESSION] 🔍 Looking for stale sessions (cutoff={cutoff}, {minutes} min ago)")
    
    # Find sessions needing summary:
    # 1. Open + customer inactive > 5 min + no summary yet
    # 2. Closed + no summary yet + at least 1 min old (avoid processing too early)
    stale = WhatsAppConversation.query.filter(
        WhatsAppConversation.summary_created == False,
        or_(
            # Case 1: Open but stale
            (WhatsAppConversation.is_open == True) & 
            (WhatsAppConversation.last_customer_message_at < cutoff),
            # Case 2: Closed without summary + at least 1 min old
            # 🔥 FIX: Add minimum age to avoid processing sessions closed just now
            (WhatsAppConversation.is_open == False) &
            (WhatsAppConversation.updated_at < datetime.utcnow() - timedelta(minutes=1))
        )
    ).all()
    
    logger.info(f"[WA-SESSION] 🔍 Found {len(stale)} sessions needing summary")
    
    return stale


def extract_memory_patch_from_messages(messages: list, lead: 'Lead') -> Optional[Dict[str, Any]]:
    """Extract customer profile updates from conversation messages
    
    Uses AI to identify new information about the customer that should be added
    to their profile (name, preferences, service interests, etc.)
    
    Args:
        messages: List of message dicts with direction and body
        lead: Lead object for context
    
    Returns:
        Dict with profile updates or None if no updates found
    """
    import os
    
    if not messages or len(messages) < 2:
        return None
    
    # Build conversation text
    conversation_text = ""
    for m in messages:
        speaker = "לקוח" if m["direction"] == "in" else "עסק"
        conversation_text += f"{speaker}: {m['body']}\n"
    
    prompt = f"""נתח את השיחה הבאה וחלץ מידע על הלקוח. החזר JSON עם השדות הבאים (רק אם הם מוזכרים בשיחה):
- name: שם הלקוח (אם נאמר)
- city: עיר (אם נאמרה)
- service_interest: סוג השירות המבוקש
- preferences: העדפות מיוחדות
- notes: הערות נוספות

אם לא מצאת מידע חדש, החזר {{}}.

שיחה:
{conversation_text}

JSON:"""
    
    try:
        import openai
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("[WA-SESSION] No OpenAI API key for memory extraction")
            return None
        
        client = openai.OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract customer information from Hebrew conversations. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.0
        )
        
        content = response.choices[0].message.content
        if not content or content.strip() == "{}":
            return None
        
        # Parse JSON response
        import json
        memory_patch = json.loads(content.strip())
        
        # Don't overwrite existing reliable data with low-confidence extractions
        # Only update if the field is empty or the new value seems more reliable
        if memory_patch:
            logger.info(f"[WA-SESSION] Extracted memory patch: {memory_patch}")
            return memory_patch
        
        return None
        
    except Exception as e:
        logger.warning(f"[WA-SESSION] Failed to extract memory patch: {e}")
        return None


def merge_customer_profile(existing_profile: Dict[str, Any], memory_patch: Dict[str, Any]) -> Dict[str, Any]:
    """Intelligently merge memory patch into customer profile
    
    Rules:
    - Don't overwrite explicit user data with AI extractions
    - Track confidence scores and data sources
    - Preserve reliable information over uncertain information
    
    Args:
        existing_profile: Current customer profile dict
        memory_patch: New information to merge
    
    Returns:
        Merged profile dict
    """
    import copy
    
    # Make a copy to avoid modifying the original
    profile = copy.deepcopy(existing_profile) if existing_profile else {}
    
    for key, value in memory_patch.items():
        if not value:  # Skip empty values
            continue
        
        # If field doesn't exist, add it
        if key not in profile:
            profile[key] = {
                'value': value,
                'source': 'ai_extraction',
                'confidence': 'low',
                'updated_at': datetime.utcnow().isoformat()
            }
        else:
            # Field exists - only update if new value seems more reliable
            existing_value = profile[key]
            
            # If existing value is from manual input, don't overwrite
            if isinstance(existing_value, dict) and existing_value.get('source') == 'manual':
                logger.debug(f"[MEMORY-MERGE] Keeping manual value for {key}")
                continue
            
            # If values are different, update with note about change
            if isinstance(existing_value, dict):
                old_val = existing_value.get('value')
            else:
                old_val = existing_value
            
            if old_val != value:
                profile[key] = {
                    'value': value,
                    'source': 'ai_extraction',
                    'confidence': 'low',
                    'updated_at': datetime.utcnow().isoformat(),
                    'previous_value': old_val
                }
                logger.debug(f"[MEMORY-MERGE] Updated {key}: {old_val} → {value}")
    
    return profile


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
    # 🔥 FIX: Filter by to_number (used for both inbound and outbound in this schema)
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
    
    🔥 FIX: Generate summary even for short conversations (1+ messages)
    
    Args:
        session: WhatsAppConversation object
    
    Returns:
        Summary text or None if failed
    """
    import os
    
    messages = get_session_messages(session)
    
    # 🔥 FIX: Require at least 1 message (was 2, too strict!)
    if not messages or len(messages) < 1:
        logger.info(f"[WA-SESSION] No messages for summary (session={session.id})")
        return None
    
    # Count customer messages to ensure there's actual conversation
    customer_messages = [m for m in messages if m["direction"] == "in"]
    if not customer_messages:
        logger.info(f"[WA-SESSION] No customer messages for summary (session={session.id})")
        return None
    
    conversation_text = ""
    for m in messages:
        speaker = "לקוח" if m["direction"] == "in" else "עסק"
        conversation_text += f"{speaker}: {m['body']}\n"
    
    # 🔥 ADD: Include conversation length context for AI
    msg_count = len(messages)
    customer_count = len(customer_messages)
    context_note = f"\n\n(שיחה: {msg_count} הודעות, {customer_count} מהלקוח)\n"
    
    # 🔥 DYNAMIC STATUSES: Fetch business-specific statuses for intelligent recommendation
    status_context = ""
    if session.business_id:
        try:
            from server.models_sql import LeadStatus
            statuses = LeadStatus.query.filter_by(
                business_id=session.business_id,
                is_active=True
            ).all()
            
            if statuses:
                # Build list with Hebrew labels ONLY
                status_list = []
                for s in statuses:
                    hebrew_label = s.label  # 🔥 FIX: Use 'label' not 'display_name'
                    status_list.append(f"- {hebrew_label}")
                
                status_context = f"""

🎯 **סטטוסים זמינים בעסק זה**:
{chr(10).join(status_list)}

⚠️ חשוב: 
- המלץ רק על סטטוס מהרשימה!
- כתוב את השם **בעברית בדיוק** כפי שמופיע ברשימה
- לא קוד באנגלית!"""
                
                logger.info(f"[WA-SESSION] Loaded {len(statuses)} statuses for business {session.business_id}")
            else:
                logger.warning(f"[WA-SESSION] No statuses found for business {session.business_id}")
        except Exception as e:
            logger.error(f"[WA-SESSION] Failed to load statuses: {e}")
    
    prompt = f"""סכם את שיחת ה-WhatsApp הבאה בעברית.

שיחה:
{conversation_text}{context_note}{status_context}

הסיכום חייב לכלול:
1. **נושא** - מה הלקוח רצה/שאל
2. **מה נדון** - הנקודות העיקריות עם **כל הפרטים הרלוונטיים** שהלקוח סיפק (תאריכים, מקומות, כמויות, דרישות וכו')
3. **תוצאה** - מה סוכם או איך הסתיימה השיחה
4. **המשך** - אם יש פעולה נדרשת
5. **המלצת סטטוס** - המלצה חכמה לסטטוס מהרשימה למעלה

כללים:
- **כתוב את כל הפרטים המשמעותיים** שהלקוח מסר (תאריכים, מספרים, מיקומים, דרישות מיוחדות)
- אם השיחה קצרה/לא הגיעה לסיכום - ציין זאת בקצרה
- סיכום יכול להיות ארוך אם השיחה הייתה מפורטת
- גם שיחה של הודעה אחת צריכה סיכום (למשל: "לקוח שאל על X, טרם נענה")
- הוסף המלצת סטטוס בפורמט [המלצה: <תווית_בעברית>]
- הסטטוס חייב להיות **בעברית** מהרשימה שקיבלת!
- **חשוב**: כתוב את הסטטוס בעברית - לא באנגלית!

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
                {"role": "system", "content": """אתה מסכם שיחות WhatsApp עסקיות בעברית.

הסיכום שלך חייב להיות:
- **מפורט** - כלול את כל הפרטים המשמעותיים שהלקוח מסר
- **מדויק** - רק מה שנאמר בפועל
- **שימושי** - מה קרה ומה הצעד הבא
- **ישיר** - אם לא הגיעו לסיכום, כתוב את זה
- **מלא** - כולל המלצה חכמה לסטטוס

חשוב במיוחד:
⚠️ רשום את **כל הפרטים הרלוונטיים** מהשיחה - תאריכים, מיקומים, מספרים, דרישות מיוחדות
⚠️ אל תכתוב "הלקוח סיפק פרטים" - **מהם הפרטים?**
⚠️ אל תסכם סיכום - כתוב את המידע בפועל

המלצת סטטוס:
⚠️ תקבל רשימת סטטוסים בעברית בפרומפט
⚠️ בחר אחד מהסטטוסים המופיעים ברשימה
⚠️ כתוב אותו **בדיוק** כפי שמופיע ברשימה (באותיות, רווחים וכו')
⚠️ בחר את הסטטוס שהכי מתאים לתוכן השיחה

דוגמאות טובות:
✓ "לקוח מבקש הובלה מתל אביב לרמלה. קומת איסוף: 2 עם מעלית, קומת פריקה: 1. 4 נפשות, 3 חדרים. העסק יכין הצעת מחיר. [המלצה: מחכה להצעת מחיר]"
✓ "בירור על זמינות למועד 15/3 בשעה 10:00. לא נמצא זמן מתאים. הלקוח יחזור בשבוע הבא. [המלצה: המתנה]"

דוגמאות רעות ❌:
❌ "הלקוח סיפק פרטים על ההובלה" - מהם הפרטים??
❌ "נדונו הנושאים הבאים" - מהם הנושאים??

זכור: השתמש רק בשמות הפנימיים מהרשימה שקיבלת!"""},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,  # 🔥 FIX: Increased for detailed summaries
            temperature=0.0
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
    1. Find sessions inactive for 5+ minutes
    2. Generate AI summaries
    3. Close sessions and update leads
    
    DB RESILIENCE: Individual session processing errors don't stop the batch
    """
    stale = get_stale_sessions()
    
    if not stale:
        logger.debug("[WA-SESSION] No stale sessions to process")
        return 0
    
    logger.info(f"[WA-SESSION] 📱 Found {len(stale)} stale sessions to process")
    
    processed = 0
    failed = 0
    no_summary = 0
    
    for session in stale:
        try:
            logger.info(f"[WA-SESSION] Processing session {session.id} (customer={session.customer_wa_id[:8]}...)")
            
            summary = generate_session_summary(session)
            
            if summary:
                logger.info(f"[WA-SESSION] ✅ Generated summary for session {session.id}: {summary[:80]}...")
                close_session(session.id, summary=summary)
                processed += 1
            else:
                logger.warning(f"[WA-SESSION] ⚠️ No summary generated for session {session.id} (too few messages)")
                # Still mark as processed to avoid infinite retries
                close_session(session.id, summary=None, mark_processed=True)
                no_summary += 1
            
        except (OperationalError, DisconnectionError) as e:
            # DB error during individual session processing - log and skip this session
            logger.error(f"[WA-SESSION] 🔴 DB error processing session {session.id}: {e}")
            failed += 1
            try:
                db.session.rollback()
            except:
                pass
            # Don't re-raise - continue with other sessions
            
        except Exception as e:
            logger.error(f"[WA-SESSION] ❌ Error processing session {session.id}: {e}")
            failed += 1
            try:
                db.session.rollback()
            except:
                pass
    
    logger.info(f"[WA-SESSION] ✅ Completed: {processed} with summary, {no_summary} without summary, {failed} failed (total {len(stale)})")
    
    return processed


def _session_processor_loop():
    """
    Background thread loop that processes stale sessions every 5 minutes.
    
    DB RESILIENCE: This loop never crashes. If DB is down (Neon endpoint disabled),
    it backs off exponentially and recovers automatically when DB returns.
    """
    logger.info("[WHATSAPP_SESSION] processor loop started interval=300s")
    logger.info("[WHATSAPP_SESSION] 📱 Background processor thread started - checking every 5 minutes")
    
    # Wait 60 seconds after startup before first check
    time.sleep(60)
    
    iteration = 0
    consecutive_errors = 0
    max_backoff = 60  # Maximum backoff: 60 seconds
    
    while True:
        iteration += 1
        backoff_sleep = 0  # Additional sleep for exponential backoff
        
        try:
            from server.app_factory import get_process_app
            from server.utils.db_health import db_ping, log_db_error, is_neon_error
            
            app = get_process_app()
            
            with app.app_context():
                # 🔥 DB RESILIENCE: Check DB health before heavy queries
                if not db_ping():
                    logger.warning("[WHATSAPP_SESSION] DB not ready, skipping cycle")
                    logger.warning(f"[WHATSAPP_SESSION] ⚠️ DB not ready, skipping cycle #{iteration}")
                    time.sleep(5)  # Short sleep before retry
                    consecutive_errors += 1
                    continue
                
                # 🔥 PRODUCTION LOGGING: Only log if stale sessions found (no "Found 0" spam)
                stale_count = len(get_stale_sessions())
                
                if stale_count > 0:
                    logger.info(f"[WHATSAPP_SESSION] 📱 Check #{iteration}: Found {stale_count} stale sessions to process")
                    
                    processed = process_stale_sessions()
                    if processed > 0:
                        logger.info(f"[WHATSAPP_SESSION] ✅ Processed {processed} stale sessions with AI summaries")
                else:
                    # 🔥 LOG SPAM FIX: Only log once per hour (12 iterations @ 5min each), and only in DEBUG mode
                    if iteration % 12 == 0:
                        logger.debug(f"[WHATSAPP_SESSION] Check #{iteration}: No stale sessions (service healthy)")
                
                # Reset error counter on success
                if consecutive_errors > 0:
                    logger.info(f"[DB_RECOVERED] op=whatsapp_session_loop after {consecutive_errors} attempts")
                    logger.error(f"[WHATSAPP_SESSION] ✅ DB recovered after {consecutive_errors} attempts")
                consecutive_errors = 0
                
        except (OperationalError, DisconnectionError) as e:
            # 🔥 DB RESILIENCE: Handle DB connectivity errors gracefully
            consecutive_errors += 1
            
            # Calculate exponential backoff: 2s → 5s → 10s → 20s → max 60s
            backoff_sleep = min(2 ** min(consecutive_errors, 5), max_backoff)
            
            # Log with Neon-specific hint if applicable
            log_db_error(e, context="whatsapp_session_loop")
            
            if is_neon_error(e):
                logger.info(f"[WHATSAPP_SESSION] 🔴 Neon endpoint disabled - backing off {backoff_sleep}s")
            else:
                logger.error(f"[WHATSAPP_SESSION] 🔴 DB error - backing off {backoff_sleep}s")
            
            logger.error(
                f"[DB_BACKOFF] service=whatsapp_session attempt={consecutive_errors} "
                f"sleep={backoff_sleep}s reason=OperationalError"
            )
            
            # Rollback and close session to prevent poisoning
            try:
                db.session.rollback()
                db.session.close()
            except:
                pass
            
            # Do NOT raise - keep loop alive
            
        except psycopg2.OperationalError as e:
            # 🔥 DB RESILIENCE: Handle psycopg2 errors (lower level than SQLAlchemy)
            consecutive_errors += 1
            backoff_sleep = min(2 ** min(consecutive_errors, 5), max_backoff)
            
            log_db_error(e, context="whatsapp_session_loop")
            
            logger.error(f"[WHATSAPP_SESSION] 🔴 Postgres error - backing off {backoff_sleep}s")
            logger.error(
                f"[DB_BACKOFF] service=whatsapp_session attempt={consecutive_errors} "
                f"sleep={backoff_sleep}s reason=psycopg2.OperationalError"
            )
            
            try:
                db.session.rollback()
                db.session.close()
            except:
                pass
            
            # Do NOT raise - keep loop alive
            
        except Exception as e:
            # 🔥 DB RESILIENCE: Catch any other errors to prevent thread death
            consecutive_errors += 1
            
            logger.error(f"[WHATSAPP_SESSION] ❌ Background processor error: {e}")
            logger.error(f"[WHATSAPP_SESSION] DB error handled - continuing loop: {e}", exc_info=True)
            
            # Shorter backoff for non-DB errors
            backoff_sleep = min(5, max_backoff)
            
            try:
                db.session.rollback()
            except:
                pass
        
        # Apply exponential backoff if there were errors
        if backoff_sleep > 0:
            time.sleep(backoff_sleep)
        
        # Regular check interval (5 minutes)
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_session_processor():
    """
    DEPRECATED: Session processor now runs as RQ job via scheduler service
    
    ⚠️ This function is deprecated and should not be called.
    
    To enable session processing:
    1. Deploy scheduler service with SERVICE_ROLE=scheduler
    2. Jobs are automatically enqueued every 5 minutes via server/scheduler/run_scheduler.py
    
    Raises:
        RuntimeError: In production mode, to catch usage errors quickly
    """
    import os
    
    # In production, fail fast to catch errors
    if os.getenv('PRODUCTION', '0') in ('1', 'true', 'True'):
        raise RuntimeError(
            "start_session_processor() is DEPRECATED and disabled in production. "
            "Use scheduler service (SERVICE_ROLE=scheduler) instead. "
            "See: server/scheduler/run_scheduler.py"
        )
    
    # In development, just warn
    logger.warning("⚠️ [WA-SESSION] start_session_processor() is deprecated")
    logger.warning("   Session processing is now handled by scheduler service + RQ jobs")
    logger.warning("   See: server/scheduler/run_scheduler.py")
    logger.warning("   Jobs: server/jobs/whatsapp_sessions_cleanup_job.py")
    return False


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
