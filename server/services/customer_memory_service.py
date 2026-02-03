"""
Customer Memory Service - Unified memory management for calls + WhatsApp
Provides customer context and history across all communication channels
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from server.models_sql import Lead, LeadNote, BusinessSettings
from server.db import db

logger = logging.getLogger(__name__)


def get_customer_memory(lead_id: int, business_id: int, max_notes: int = 5) -> Dict[str, Any]:
    """Load unified customer memory for AI context
    
    This function loads:
    1. Customer profile (customer_profile_json)
    2. Last conversation summary (last_summary)
    3. Last 5 customer service notes (AI-generated or manual)
    4. Interaction history metadata
    
    Args:
        lead_id: Lead ID to load memory for
        business_id: Business ID for security check
        max_notes: Maximum number of recent notes to include (default: 5)
    
    Returns:
        Dict with customer memory data for AI context
    """
    try:
        # Load lead
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=business_id
        ).first()
        
        if not lead:
            logger.warning(f"[MEMORY] ⚠️ Lead {lead_id} not found for business {business_id}")
            return {}
        
        logger.info(f"[MEMORY] 📂 Loading unified memory for lead {lead_id}:")
        logger.info(f"   • Name: {lead.full_name or 'N/A'}")
        logger.info(f"   • Phone: {lead.phone_e164 or lead.mobile_phone or 'N/A'}")
        logger.info(f"   • Status: {lead.status or 'N/A'}")
        logger.info(f"   • Last Channel: {lead.last_channel or 'N/A'}")
        logger.info(f"   • Last Interaction: {lead.last_interaction_at.isoformat() if lead.last_interaction_at else 'Never'}")
        
        # Build memory dict
        memory = {
            'lead_id': lead.id,
            'customer_name': lead.full_name,
            'customer_profile': lead.customer_profile_json or {},
            'last_summary': lead.last_summary,
            'last_interaction_at': lead.last_interaction_at.isoformat() if lead.last_interaction_at else None,
            'last_channel': lead.last_channel,
            'phone': lead.phone_e164,
            'email': lead.email,
            'status': lead.status
        }
        
        # Load last N customer service notes (prioritize AI-generated call summaries)
        notes = LeadNote.query.filter_by(
            lead_id=lead_id,
            tenant_id=business_id
        ).filter(
            LeadNote.note_type.in_(['call_summary', 'manual'])
        ).order_by(
            LeadNote.created_at.desc()
        ).limit(max_notes).all()
        
        # Format notes for AI context
        recent_notes = []
        for note in notes:
            recent_notes.append({
                'content': note.content,
                'type': note.note_type,
                'created_at': note.created_at.isoformat() if note.created_at else None,
                'structured_data': note.structured_data or {}
            })
        
        memory['recent_notes'] = recent_notes
        
        # 🔥 LOG: Summary of loaded memory
        profile_fields = len(memory['customer_profile']) if memory['customer_profile'] else 0
        logger.info(f"[MEMORY] ✅ Memory loaded successfully:")
        logger.info(f"   • Profile Fields: {profile_fields}")
        logger.info(f"   • Last Summary: {'Yes' if memory['last_summary'] else 'No'} ({len(memory['last_summary'] or '')} chars)")
        logger.info(f"   • Recent Notes: {len(recent_notes)} (call_summary + manual)")
        if recent_notes:
            for i, note in enumerate(recent_notes[:3], 1):  # Show first 3
                logger.info(f"      [{i}] {note['type']}: {note['content'][:60]}...")
        
        return memory
        
    except Exception as e:
        logger.error(f"[MEMORY] Failed to load customer memory for lead {lead_id}: {e}")
        return {}


def format_memory_for_ai(memory: Dict[str, Any]) -> str:
    """Format customer memory as human-readable text for AI context
    
    Args:
        memory: Memory dict from get_customer_memory()
    
    Returns:
        Formatted string for AI system message
    """
    if not memory:
        return ""
    
    parts = []
    
    # Customer profile
    profile = memory.get('customer_profile', {})
    if profile:
        parts.append("📋 פרופיל לקוח:")
        for key, value in profile.items():
            if isinstance(value, dict):
                val = value.get('value', value)
            else:
                val = value
            if val:
                parts.append(f"  • {key}: {val}")
    
    # Last interaction summary
    if memory.get('last_summary'):
        parts.append("\n📝 סיכום שיחה אחרונה:")
        parts.append(f"  {memory['last_summary']}")
        if memory.get('last_channel'):
            parts.append(f"  (ערוץ: {memory['last_channel']})")
    
    # Recent notes (last 5 = most recent first)
    recent_notes = memory.get('recent_notes', [])
    if recent_notes:
        parts.append("\n📚 הערות אחרונות (האחרונה היא הכי עדכנית):")
        for i, note in enumerate(recent_notes, 1):
            note_type = "סיכום שיחה" if note['type'] == 'call_summary' else "הערה"
            parts.append(f"  {i}. [{note_type}] {note['content'][:100]}...")
    
    return "\n".join(parts) if parts else ""


def should_ask_continue_or_fresh(lead_id: int, business_id: int) -> bool:
    """Check if we should ask customer "continue or start fresh?"
    
    This checks if:
    1. Customer has previous interaction history
    2. Customer has a last_summary
    3. It's been more than 15 minutes since last interaction
    
    Args:
        lead_id: Lead ID
        business_id: Business ID
    
    Returns:
        True if should ask, False otherwise
    """
    try:
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=business_id
        ).first()
        
        if not lead:
            return False
        
        # Must have previous interaction and summary
        if not lead.last_summary or not lead.last_interaction_at:
            return False
        
        # Check if it's been more than 15 minutes
        from datetime import timedelta
        time_since_last = datetime.utcnow() - lead.last_interaction_at
        
        # Ask if it's been more than 15 minutes but less than 7 days
        if timedelta(minutes=15) < time_since_last < timedelta(days=7):
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"[MEMORY] Failed to check continue/fresh for lead {lead_id}: {e}")
        return False


def is_customer_service_enabled(business_id: int) -> bool:
    """Check if customer service mode is enabled for this business
    
    Args:
        business_id: Business ID
    
    Returns:
        True if enabled, False otherwise
    """
    try:
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        if settings:
            return settings.enable_customer_service or False
        return False
    except Exception as e:
        logger.error(f"[MEMORY] Failed to check customer service setting: {e}")
        return False


def update_interaction_timestamp(lead_id: int, business_id: int, channel: str):
    """Update lead's last_interaction_at and last_channel
    
    Args:
        lead_id: Lead ID
        business_id: Business ID
        channel: 'whatsapp' or 'call'
    """
    try:
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=business_id
        ).first()
        
        if lead:
            lead.last_interaction_at = datetime.utcnow()
            lead.last_channel = channel
            db.session.commit()
            logger.debug(f"[MEMORY] Updated interaction timestamp for lead {lead_id}, channel={channel}")
    except Exception as e:
        logger.error(f"[MEMORY] Failed to update interaction timestamp: {e}")
        db.session.rollback()
