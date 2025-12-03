"""
BUILD 163: Monday.com Webhook Integration Service
Sends call transcripts and metadata to Monday.com via webhooks
"""
import logging
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def send_call_transcript_to_monday(*, business, call, transcript: str) -> None:
    """
    If the business enabled Monday integration, send a JSON payload with call
    details + transcript to the configured monday_webhook_url.

    This function must NEVER break the main call flow. If it fails,
    log a warning and return.
    
    Args:
        business: Business model or object with settings (can be Business or BusinessSettings)
        call: CallLog model with call details
        transcript: Full call transcript text
    """
    try:
        from server.models_sql import BusinessSettings
        
        settings = None
        monday_webhook_url = None
        send_transcripts = False
        business_id = None
        business_name = "Unknown"
        
        logger.info(f"[MONDAY] 🔍 Starting Monday webhook check for business: {getattr(business, 'id', 'N/A')}")
        
        if hasattr(business, 'id'):
            business_id = business.id
            business_name = getattr(business, 'name', 'Unknown')
            settings = BusinessSettings.query.filter_by(tenant_id=business.id).first()
            logger.info(f"[MONDAY] 🔍 Loaded settings for business {business_id}: settings_found={settings is not None}")
        else:
            logger.warning(f"[MONDAY] ⚠️ Business object has no 'id' attribute: {type(business)}")
            return
        
        if settings:
            monday_webhook_url = settings.monday_webhook_url
            send_transcripts = settings.send_call_transcripts_to_monday
            logger.info(f"[MONDAY] 🔍 Settings: URL={bool(monday_webhook_url)}, enabled={send_transcripts}, URL_prefix={monday_webhook_url[:50] if monday_webhook_url else 'None'}...")
        else:
            logger.warning(f"[MONDAY] ⚠️ No BusinessSettings found for tenant_id={business_id}")
            return
        
        if not monday_webhook_url:
            logger.info(f"[MONDAY] ⏭️ Skipping - no webhook URL configured for business {business_id}")
            return
            
        if not send_transcripts:
            logger.info(f"[MONDAY] ⏭️ Skipping - send_call_transcripts_to_monday=False for business {business_id}")
            return
        
        call_data = {
            "call_id": call.id if hasattr(call, 'id') else None,
            "call_sid": call.call_sid if hasattr(call, 'call_sid') else None,
            "direction": call.direction if hasattr(call, 'direction') else "inbound",
            "from_number": call.from_number if hasattr(call, 'from_number') else None,
            "to_number": call.to_number if hasattr(call, 'to_number') else None,
            "duration_sec": call.duration if hasattr(call, 'duration') else 0,
            "started_at": call.created_at.isoformat() if hasattr(call, 'created_at') and call.created_at else None,
            "ended_at": datetime.utcnow().isoformat(),
        }
        
        payload = {
            "source": "prosaas_call_center",
            "business_id": business_id,
            "business_name": business_name,
            **call_data,
            "transcript": transcript
        }
        
        transcript_preview = transcript[:100] if transcript else "(empty)"
        logger.info(f"[MONDAY] 📤 Sending transcript to Monday for business {business_id}, call {call_data.get('call_id')}")
        logger.info(f"[MONDAY] 📤 Payload: call_sid={call_data.get('call_sid')}, duration={call_data.get('duration_sec')}s, transcript_len={len(transcript) if transcript else 0}")
        logger.info(f"[MONDAY] 📤 Transcript preview: {transcript_preview}...")
        logger.info(f"[MONDAY] 📤 Webhook URL: {monday_webhook_url}")
        
        response = requests.post(
            monday_webhook_url,
            json=payload,
            timeout=10,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ProSaaS-CallCenter/1.0"
            }
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"[MONDAY] ✅ Successfully sent transcript to Monday. Status: {response.status_code}, Response: {response.text[:100]}")
        else:
            logger.warning(f"[MONDAY] ❌ Monday webhook FAILED - Status {response.status_code}: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        logger.warning(f"[MONDAY] ❌ TIMEOUT sending transcript to Monday webhook (10s limit)")
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"[MONDAY] ❌ CONNECTION ERROR sending to Monday webhook: {e}")
    except Exception as e:
        logger.warning(f"[MONDAY] ❌ UNEXPECTED ERROR sending transcript to Monday: {e}", exc_info=True)


def send_whatsapp_transcript_to_monday(*, business, lead, transcript: str, conversation_id: Optional[int] = None) -> None:
    """
    If the business enabled Monday integration, send WhatsApp conversation transcript.
    
    Args:
        business: Business model with settings
        lead: Lead model (customer info)
        transcript: Full conversation transcript
        conversation_id: Optional WhatsApp conversation ID
    """
    try:
        from server.models_sql import BusinessSettings
        
        settings = None
        monday_webhook_url = None
        send_transcripts = False
        business_id = None
        business_name = "Unknown"
        
        if hasattr(business, 'id'):
            business_id = business.id
            business_name = getattr(business, 'name', 'Unknown')
            settings = BusinessSettings.query.filter_by(tenant_id=business.id).first()
        
        if settings:
            monday_webhook_url = settings.monday_webhook_url
            send_transcripts = settings.send_call_transcripts_to_monday
        
        if not monday_webhook_url or not send_transcripts:
            logger.debug(f"[MONDAY] Skipping WhatsApp webhook for business {business_id}")
            return
        
        payload = {
            "source": "prosaas_whatsapp",
            "business_id": business_id,
            "business_name": business_name,
            "channel": "whatsapp",
            "conversation_id": conversation_id,
            "lead_id": lead.id if hasattr(lead, 'id') else None,
            "customer_name": lead.name if hasattr(lead, 'name') else None,
            "customer_phone": lead.phone if hasattr(lead, 'phone') else None,
            "ended_at": datetime.utcnow().isoformat(),
            "transcript": transcript
        }
        
        logger.info(f"[MONDAY] Sending WhatsApp transcript to Monday for business {business_id}")
        
        response = requests.post(
            monday_webhook_url,
            json=payload,
            timeout=10,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ProSaaS-CallCenter/1.0"
            }
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"[MONDAY] ✅ Successfully sent WhatsApp transcript to Monday")
        else:
            logger.warning(f"[MONDAY] ⚠️ Monday webhook returned status {response.status_code}")
            
    except Exception as e:
        logger.warning(f"[MONDAY] ⚠️ Error sending WhatsApp transcript to Monday: {e}")
