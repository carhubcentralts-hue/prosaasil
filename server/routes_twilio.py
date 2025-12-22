"""
Hebrew AI Call Center - Twilio Routes FIXED לפי ההנחיות המדויקות
שלב 4: שיחות → לידים + תמלול אוטומטי
Build 89: ImportError Fix + Immediate call_log Creation
Build 96: Logger Fix - Added logging import
"""
import os
import time
import logging
import threading
from flask import Blueprint, request, current_app, make_response, Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from server.stream_state import stream_registry
from server.twilio_security import require_twilio_signature
from server.extensions import csrf

# ייבוא מראש למניעת עיכובים ב-webhooks
from server.tasks_recording import save_call_status, enqueue_recording
from server.models_sql import db, Business, Customer, CallLog, Lead
from sqlalchemy.orm import sessionmaker

# ✅ BUILD 89: Import למעלה למניעת ImportError בthread
from server.services.customer_intelligence import CustomerIntelligence

# ✅ BUILD 96: Logger setup
logger = logging.getLogger(__name__)

# Call Status Constants - Max 32 chars (status field limit)
CALL_STATUS_INITIATED = "initiated"
CALL_STATUS_IN_PROGRESS = "in_progress"
CALL_STATUS_STREAMING = "streaming"

# Early-stage call statuses that can be updated by AMD (set for O(1) lookup)
EARLY_STAGE_STATUSES = {CALL_STATUS_INITIATED, CALL_STATUS_IN_PROGRESS, CALL_STATUS_STREAMING}

# AMD Status Constants - Max 32 chars (status field limit)
AMD_STATUS_VOICEMAIL = "voicemail"  # Generic voicemail/machine
AMD_STATUS_HUMAN = "answered_human"  # Human answered

twilio_bp = Blueprint("twilio", __name__)
# Backwards-compatible alias used by pre-deploy smoke checks / older imports.
routes_twilio_bp = twilio_bp

def _twiml(vr: VoiceResponse) -> Response:
    """
    ✅ תיקון Error 12100: החזרת TwiML תקין עם Twilio SDK
    """
    xml = str(vr)
    resp = Response(xml, status=200)
    resp.headers['Content-Type'] = 'application/xml'
    return resp

def abs_url(path: str) -> str:
    """Generate absolute URL for TwiML - תיקון קריטי להסבת https://"""
    scheme = (request.headers.get("X-Forwarded-Proto") or "https").split(",")[0].strip()
    host   = (request.headers.get("X-Forwarded-Host")  or request.host).split(",")[0].strip()
    base   = f"{scheme}://{host}"
    return f"{base}{path}"

def _watchdog(call_sid, wss_host, start_timeout=6, no_media_timeout=6):
    """Watchdog to redirect calls if WebSocket fails"""
    time.sleep(start_timeout)
    st = stream_registry.get(call_sid)
    if not st.get("started"):
        _do_redirect(call_sid, wss_host, reason="no_stream_start")
        return
    if time.time() - st.get("last_media_at", 0) > no_media_timeout:
        _do_redirect(call_sid, wss_host, reason="no_media")

def _do_redirect(call_sid, wss_host, reason):
    """Watchdog redirect function"""
    current_app.logger.warning("WATCHDOG_REDIRECT", extra={"call_sid": call_sid, "reason": reason})
    # ✅ FIX: Prefer PUBLIC_HOST in production, then dev domain for local testing
    public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
    host = public_host or os.environ.get('REPLIT_DEV_DOMAIN') or os.environ.get('REPLIT_DOMAINS', '').split(',')[0] or 'localhost'
    # ✅ FIX Error 12100: NO leading spaces/whitespace in XML tags
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Record playBeep="false" timeout="4" maxLength="30" transcribe="false" action="https://{host}/webhook/handle_recording"/></Response>'
    try:
        # Use Deployment ENV vars (critical for production)
        client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        client.calls(call_sid).update(twiml=twiml)
        current_app.logger.info("WATCHDOG_REDIRECT_OK", extra={"call_sid": call_sid})
    except Exception:
        current_app.logger.exception("WATCHDOG_REDIRECT_FAIL")

def _start_recording_from_second_zero(call_sid, from_number="", to_number=""):
    """
    🔥 FIX: Start recording from second 0 using Twilio REST API
    This runs in background thread and does NOT block TwiML response.
    
    Recording will capture the ENTIRE call including AI greeting.
    Logs: [REC_START] when initiated, [REC_CB] on completion callback
    """
    import time
    start_timestamp = time.time()
    
    try:
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            print(f"❌ [REC_START] Missing Twilio credentials call_sid={call_sid}")
            logger.error(f"[REC_START] Missing Twilio credentials call_sid={call_sid}")
            return
        
        # Get host for callback URL
        public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
        if not public_host:
            print(f"⚠️ [REC_START] PUBLIC_HOST not set, using fallback call_sid={call_sid}")
            logger.warning(f"[REC_START] PUBLIC_HOST not set call_sid={call_sid}")
            # We still need to try - use a reasonable fallback
            public_host = os.environ.get('REPLIT_DEV_DOMAIN') or os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
        
        if not public_host:
            print(f"❌ [REC_START] No host available for callback URL call_sid={call_sid}")
            logger.error(f"[REC_START] No host available for callback URL call_sid={call_sid}")
            return
        
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        
        # 🔥 COST OPTIMIZATION: Start recording with SINGLE channel (not dual)
        # Single channel is sufficient for transcription and saves 10-15% per call
        # Recording will continue until call ends
        recording_callback_url = f"https://{public_host}/webhook/recording_status"
        
        print(f"🎙️ [REC_START] call_sid={call_sid} ts={start_timestamp:.2f}")
        logger.info(f"[REC_START] call_sid={call_sid} ts={start_timestamp:.2f} callback={recording_callback_url}")
        
        try:
            recording = client.calls(call_sid).recordings.create(
                recording_channels='single',  # 🔥 COST OPTIMIZATION: Single channel (10-15% savings)
                recording_status_callback=recording_callback_url,
                recording_status_callback_event=['completed']  # Only notify when recording completes
            )
            
            elapsed_ms = int((time.time() - start_timestamp) * 1000)
            print(f"✅ [REC_START] SUCCESS call_sid={call_sid} recording_sid={recording.sid} elapsed={elapsed_ms}ms")
            logger.info(f"[REC_START] SUCCESS call_sid={call_sid} recording_sid={recording.sid} elapsed={elapsed_ms}ms")
            
            # Save recording_sid to CallLog immediately
            try:
                from server.app_factory import get_process_app
                app = get_process_app()
                with app.app_context():
                    from server.models_sql import CallLog, db
                    call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                    if call_log:
                        call_log.recording_sid = recording.sid
                        db.session.commit()
                        print(f"✅ [REC_START] Saved recording_sid={recording.sid} to CallLog")
                    else:
                        print(f"⚠️ [REC_START] CallLog not found call_sid={call_sid}")
            except Exception as e:
                print(f"⚠️ [REC_START] Failed to save recording_sid: {e}")
                logger.warning(f"[REC_START] Failed to save recording_sid call_sid={call_sid}: {e}")
                
        except Exception as e:
            elapsed_ms = int((time.time() - start_timestamp) * 1000)
            print(f"❌ [REC_START] FAILED call_sid={call_sid} elapsed={elapsed_ms}ms error={e}")
            logger.error(f"[REC_START] FAILED call_sid={call_sid} elapsed={elapsed_ms}ms error={e}")
            
    except Exception as e:
        print(f"❌ [REC_START] CRITICAL_ERROR call_sid={call_sid} error={e}")
        logger.error(f"[REC_START] CRITICAL_ERROR call_sid={call_sid} error={e}")

def _trigger_recording_for_call(call_sid):
    """חפש או עורר הקלטה לשיחה לאחר שהזרם נגמר"""
    try:
        # וידוא שיש אישורי Twilio
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            print(f"❌ Missing Twilio credentials for recording {call_sid}")
            return
            
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        
        # קודם נחפש הקלטות קיימות לשיחה
        try:
            recordings = client.recordings.list(call_sid=call_sid, limit=5)
            
            if recordings:
                # נמצאו הקלטות - נעבד אותן
                for recording in recordings:
                    print(f"✅ Found existing recording for {call_sid}: {recording.uri}")
                    
                    # ✅ CRITICAL FIX: Save recording_url to CallLog IMMEDIATELY
                    # This ensures the worker can access the recording
                    try:
                        from server.app_factory import get_process_app
                        app = get_process_app()
                        with app.app_context():
                            from server.models_sql import CallLog, db
                            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                            if call_log:
                                call_log.recording_url = recording.uri
                                db.session.commit()
                                print(f"✅ Saved recording_url to CallLog for {call_sid}: {recording.uri}")
                            else:
                                print(f"⚠️ CallLog not found for {call_sid}, recording_url not saved")
                    except Exception as e:
                        print(f"⚠️ Failed to save recording_url to CallLog: {e}")
                    
                    # קבל פרטי השיחה למספרי טלפון
                    from_num = ''
                    to_num = ''
                    try:
                        call = client.calls(call_sid).fetch()
                        from_num = getattr(call, 'from_', '') or str(getattr(call, 'from_formatted', '') or '')
                        to_num = getattr(call, 'to', '') or str(getattr(call, 'to_formatted', '') or '')
                    except Exception as e:
                        print(f"⚠️ Could not get call details: {e}")
                    
                    # בנה form data כמו webhook של Twilio
                    # ✅ FIX: Use recording.uri as-is (יחסי, מסתיים ב-.json)
                    # download_recording ידאג לנסות כמה וריאציות
                    form_data = {
                        'CallSid': call_sid,
                        'RecordingUrl': recording.uri,
                        'RecordingDuration': str(recording.duration),
                        'RecordingStatus': recording.status,
                        'From': from_num,
                        'To': to_num
                    }
                    
                    # שלח לעיבוד
                    enqueue_recording(form_data)
                    print(f"✅ Recording queued for processing: {call_sid}")
                    return
                    
        except Exception as e:
            print(f"⚠️ Error checking recordings for {call_sid}: {e}")
        
        # אם אין הקלטות, נסה לעדכן השיחה לכלול Record (אם עדיין פעילה)
        try:
            call = client.calls(call_sid).fetch()
            
            if call.status in ['in-progress', 'ringing']:
                # השיחה עדיין פעילה - עדכן ל-Record TwiML
                # ✅ BUILD 155: PUBLIC_HOST required in production
                public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
                host = public_host or os.environ.get('REPLIT_DEV_DOMAIN') or os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
                if not host:
                    print("❌ PUBLIC_HOST not configured - cannot update call to Record")
                    return
                # ✅ FIX Error 12100: NO leading spaces/whitespace in XML tags
                record_twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Record playBeep="false" timeout="30" maxLength="300" transcribe="false" action="https://{host}/webhook/handle_recording"/></Response>'
                
                try:
                    client.calls(call_sid).update(twiml=record_twiml)
                    print(f"✅ Updated call {call_sid} to Record TwiML")
                except Exception as e:
                    print(f"⚠️ Could not update call {call_sid} (may have ended): {e}")
            else:
                print(f"ℹ️ Call {call_sid} ended without recording (status: {call.status})")
                
        except Exception as e:
            print(f"⚠️ Error updating call {call_sid}: {e}")
            
    except Exception as e:
        print(f"❌ Failed to trigger recording for {call_sid}: {e}")

def _create_lead_from_call(call_sid, from_number, to_number=None, business_id=None):
    """
    ✅ BUILD 89: יצירת/עדכון ליד אוטומטי - עם try/except מלא
    Thread-safe: רץ בהקשר נפרד עם app context
    ✅ BUILD 152: הסרת hardcoded phone number - זיהוי דינמי לפי Business.phone_e164
    """
    from server.app_factory import get_process_app
    
    # ✅ BUILD 152: to_number יקבע דינמית לפי עסק פעיל (אם חסר)
    
    print(f"🔵 CREATE_LEAD_FROM_CALL - Starting for {from_number}, call_sid={call_sid}")
    
    try:
        # 🔥 Get app WITHOUT creating new instance
        app = get_process_app()
        with app.app_context():
            from server.models_sql import CallLog, Business, Lead
            from server.db import db
            
            print(f"🔵 CREATE_LEAD_FROM_CALL - App context created")
            
            # ✅ BUILD 100 FIX: זיהוי business לפי to_number - שימוש ב-phone_e164
            if not business_id:
                from sqlalchemy import or_
                if to_number:
                    normalized_phone = to_number.strip().replace('-', '').replace(' ', '')
                    biz = Business.query.filter(
                        or_(
                            Business.phone_e164 == to_number,
                            Business.phone_e164 == normalized_phone
                        )
                    ).first()
                    if biz:
                        business_id = biz.id
                        print(f"✅ Thread resolved business_id={business_id} from to_number={to_number} (Business: {biz.name})")
                
                if not business_id:
                    biz = Business.query.filter_by(is_active=True).first()
                    if biz:
                        business_id = biz.id
                        print(f"⚠️ Thread using fallback active business_id={business_id}")
                    else:
                        print(f"❌ No business found for call {call_sid} - skipping lead creation")
                        return  # Don't create leads without valid business
            
            # ✅ שלב 1: עדכן call_log (אם כבר נוצר ב-incoming_call) עם customer_id
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            
            # ✅ שלב 2: יצירת/עדכון customer + lead (עם try/except פנימי)
            customer = None
            lead = None
            try:
                from server.services.customer_intelligence import CustomerIntelligence
                ci_service = CustomerIntelligence(business_id=business_id)
                customer, lead, was_created = ci_service.find_or_create_customer_from_call(
                    phone_number=from_number,
                    call_sid=call_sid,
                    transcription="",
                    conversation_data={}
                )
                print(f"✅ CustomerIntelligence SUCCESS: customer_id={customer.id if customer else None}, lead_id={lead.id if lead else None}, was_created={was_created}")
                logger.info(f"✅ LEAD_CREATED: business_id={business_id}, lead_id={lead.id if lead else None}, phone={from_number}")
            except Exception as e:
                print(f"⚠️ CustomerIntelligence failed (non-critical): {e}")
                logger.warning(f"CustomerIntelligence failed for call {call_sid}: {e}")
            
            # ✅ שלב 3: עדכן call_log עם customer_id (אם נוצר)
            if call_log and customer:
                call_log.customer_id = customer.id
                call_log.status = "in_progress"
                db.session.commit()
                print(f"✅ Updated call_log with customer_id={customer.id}")
            
            # ✅ שלב 4: fallback lead אם CustomerIntelligence נכשל
            # 🚨 CRITICAL: ALWAYS create lead if missing (user demand!)
            if not lead:
                try:
                    # Check if lead already exists for this phone
                    existing_lead = Lead.query.filter_by(
                        tenant_id=business_id,
                        phone_e164=from_number
                    ).first()
                    
                    if existing_lead:
                        lead = existing_lead
                        print(f"✅ Found existing lead ID={lead.id}")
                        logger.info(f"✅ LEAD_FOUND: lead_id={lead.id}, phone={from_number}")
                    else:
                        lead = Lead()
                        lead.tenant_id = business_id
                        lead.phone_e164 = from_number
                        lead.source = "call"
                        lead.external_id = call_sid
                        lead.status = "new"
                        lead.notes = f"שיחה נכנסת - {call_sid}"
                        db.session.add(lead)
                        db.session.commit()
                        print(f"✅ CREATED FALLBACK LEAD ID={lead.id} for phone={from_number}")
                        logger.info(f"✅ LEAD_CREATED_FALLBACK: lead_id={lead.id}, phone={from_number}, business_id={business_id}")
                except Exception as e:
                    print(f"❌ Fallback lead creation FAILED: {e}")
                    logger.error(f"Fallback lead creation failed for {call_sid}: {e}")
                    import traceback
                    traceback.print_exc()
                    db.session.rollback()
        
    except Exception as e:
        print(f"❌ CRITICAL: Thread failed for {call_sid}: {e}")
        import traceback
        traceback.print_exc()

# TwiML Preview endpoint
@csrf.exempt
@twilio_bp.route("/webhook/incoming_call_preview", methods=["GET"])
def incoming_call_preview():
    """
    ✅ Build 62: Preview with Parameter
    """
    call_sid = "CA_PREVIEW_" + str(int(time.time()))
    
    # בנה host נכון - PUBLIC_HOST מקבל עדיפות ראשונה!
    public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
    if public_host:
        host = public_host
    else:
        host = (
            request.headers.get("X-Forwarded-Host") or 
            os.environ.get('REPLIT_DEV_DOMAIN') or 
            os.environ.get('REPLIT_DOMAINS', '').split(',')[0] or 
            request.host
        ).split(",")[0].strip()
    
    # ✅ BUILD 155: Dynamic phone from first active business only
    from server.models_sql import Business
    preview_business = Business.query.filter_by(is_active=True).first()
    if not preview_business:
        return make_response("No active business configured", 503)
    preview_to_number = preview_business.phone_e164 or "preview"
    
    vr = VoiceResponse()
    connect = vr.connect(action=f"https://{host}/webhook/stream_ended")
    stream = connect.stream(url=f"wss://{host}/ws/twilio-media")
    stream.parameter(name="CallSid", value=call_sid)
    stream.parameter(name="To", value=preview_to_number)
    
    return _twiml(vr)

@csrf.exempt
@twilio_bp.route("/webhook/voice", methods=["POST", "GET"])
@require_twilio_signature
def voice_webhook():
    """
    ✅ BUILD 70: Main Twilio voice webhook - delegates to incoming_call
    This is the primary webhook URL configured in Twilio console
    """
    return incoming_call()

# ✅ BUILD 157: Add hyphen route alias for Twilio compatibility
@csrf.exempt
@twilio_bp.route("/webhook/incoming-call", methods=["POST", "GET"])
@require_twilio_signature
def incoming_call_hyphen():
    """Route alias with hyphen for Twilio webhook"""
    return incoming_call()

# ✅ BUILD 168.4: Add root-level route alias for Twilio (some configs use /incoming_call without /webhook/)
@csrf.exempt
@twilio_bp.route("/incoming_call", methods=["POST", "GET"])
@require_twilio_signature
def incoming_call_root():
    """Route alias at root level for Twilio webhook compatibility"""
    return incoming_call()

@csrf.exempt
@twilio_bp.route("/webhook/incoming_call", methods=["POST", "GET"])
@require_twilio_signature
def incoming_call():
    """
    ✅ BUILD 89: צור call_log מיד + TwiML with Twilio SDK + Parameter (CRITICAL!)
    ✅ BUILD 155: Support both GET and POST (Twilio may use either)
    """
    t0 = time.time()
    logger.info(f"[GREETING_PROFILER] incoming_call START at {t0}")
    
    # ✅ BUILD 155: Support both GET (query params) and POST (form data)
    if request.method == "GET":
        call_sid = request.args.get("CallSid", "")
        from_number = request.args.get("From", "")
        to_number = request.args.get("To", "")
        twilio_direction = request.args.get("Direction")  # 🔥 FIX: No default - None if missing
        parent_call_sid = request.args.get("ParentCallSid")  # 🔥 NEW: Capture parent call SID
    else:
        call_sid = request.form.get("CallSid", "")
        from_number = request.form.get("From", "")
        to_number = request.form.get("To", "")
        twilio_direction = request.form.get("Direction")  # 🔥 FIX: No default - None if missing
        parent_call_sid = request.form.get("ParentCallSid")  # 🔥 NEW: Capture parent call SID
    
    # ✅ BUILD 100: זיהוי business לפי to_number - חיפוש ישיר ב-Business.phone_e164 (העמודה האמיתית!)
    from server.models_sql import Business
    from sqlalchemy import or_
    
    business_id = None
    if to_number:
        normalized_phone = to_number.strip().replace('-', '').replace(' ', '')
        business = Business.query.filter(
            or_(
                Business.phone_e164 == to_number,
                Business.phone_e164 == normalized_phone
            )
        ).first()
        
        if business:
            business_id = business.id
        else:
            # Fallback: עסק פעיל ראשון
            business = Business.query.filter_by(is_active=True).first()
            if business:
                business_id = business.id
    
    # BUILD 174: Check inbound call concurrency limits
    if business_id:
        try:
            from server.services.call_limiter import check_inbound_call_limit
            allowed, reject_message = check_inbound_call_limit(business_id)
            if not allowed:
                logger.warning(f"📵 INCOMING_CALL REJECTED: business {business_id} at limit")
                vr = VoiceResponse()
                vr.say(reject_message, language="he-IL", voice="Google.he-IL-Wavenet-C")
                vr.hangup()
                return _twiml(vr)
        except Exception as e:
            logger.error(f"⚠️ Call limit check failed: {e} - allowing call")
    
    if call_sid and from_number:
        try:
            # 🔥 UPSERT: Check if call log already exists (for retry scenarios)
            from server.tasks_recording import normalize_call_direction
            
            existing = CallLog.query.filter_by(call_sid=call_sid).first()
            if not existing:
                # CREATE: New call log
                # ✅ BUILD 152: Dynamic to_number fallback (no hardcoded phone!)
                fallback_to = to_number or (business.phone_e164 if business else None) or "unknown"
                
                # 🔥 CRITICAL: Only normalize if we have a direction, otherwise use "unknown"
                if twilio_direction:
                    normalized_direction = normalize_call_direction(twilio_direction)
                else:
                    normalized_direction = "unknown"
                
                call_log = CallLog(
                    call_sid=call_sid,
                    parent_call_sid=parent_call_sid if parent_call_sid else None,  # 🔥 FIX: Explicit None
                    from_number=from_number,
                    to_number=fallback_to,  # ✅ BUILD 152: Dynamic, not hardcoded
                    business_id=business_id,
                    direction=normalized_direction,  # 🔥 NEW: Normalized direction or "unknown"
                    twilio_direction=twilio_direction if twilio_direction else None,  # 🔥 FIX: Explicit None if missing
                    call_status="initiated",  # ✅ BUILD 90: Legacy field
                    status="initiated"
                )
                db.session.add(call_log)
                db.session.commit()
                logger.info(f"✅ Created CallLog: {call_sid}, direction={normalized_direction}, twilio_direction={twilio_direction}, parent={parent_call_sid}")
            else:
                # UPDATE: Call log exists (retry scenario) - update ONLY if we have values
                # 🔥 CRITICAL: Smart update - allow upgrading from "unknown" to real value
                if parent_call_sid and not existing.parent_call_sid:
                    existing.parent_call_sid = parent_call_sid
                if twilio_direction:
                    # Update if: (1) never set, OR (2) currently "unknown"
                    if not existing.twilio_direction or existing.direction == "unknown":
                        existing.twilio_direction = twilio_direction
                        existing.direction = normalize_call_direction(twilio_direction)
                db.session.commit()
                logger.info(f"✅ Updated existing CallLog: {call_sid}")
        except Exception as e:
            logger.error(f"Failed to create/update call_log: {e}")
            db.session.rollback()
    
    # בנה host נכון - PUBLIC_HOST מקבל עדיפות ראשונה!
    public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
    if public_host:
        host = public_host
    else:
        # Fallback chain for development
        host = (
            request.headers.get("X-Forwarded-Host") or 
            os.environ.get('REPLIT_DEV_DOMAIN') or 
            os.environ.get('REPLIT_DOMAINS', '').split(',')[0] or 
            request.host
        ).split(",")[0].strip()
    
    # ✅ Twilio SDK - Simplified for Error 12100 fix
    vr = VoiceResponse()
    
    # 🎧 BUILD: Echo prevention - no greeting duplication
    # Recording starts AFTER stream ends (in stream_ended webhook)
    # This ensures clean recordings without AI greeting echo
    
    # ✅ Connect + Stream - Minimal required parameters
    # track="inbound_track" ensures only user audio is sent to AI (not AI's own voice)
    connect = vr.connect(action=f"https://{host}/webhook/stream_ended")
    stream = connect.stream(
        url=f"wss://{host}/ws/twilio-media",
        track="inbound_track"  # 🎧 Only send user audio to stream, prevents feedback
    )
    
    # ✅ CRITICAL: Parameters with CallSid + To + business_id
    stream.parameter(name="CallSid", value=call_sid)
    stream.parameter(name="To", value=to_number or "unknown")
    # 🔥 FIX #2: Pass business_id as parameter for FAST prompt loading
    if business_id:
        stream.parameter(name="business_id", value=str(business_id))
    
    # 🔥 CRITICAL: Move prompt building to background thread - DO NOT block TwiML response!
    # WebSocket connection depends on fast TwiML response
    def _prebuild_prompts_async(call_sid, business_id):
        """Background thread to pre-build prompts - doesn't block webhook response"""
        try:
            from server.services.realtime_prompt_builder import (
                build_compact_greeting_prompt,
                build_full_business_prompt,
            )
            from server.stream_state import stream_registry
            from server.app_factory import get_process_app
            
            # 🔥 BUG FIX: Wrap with app context for database queries
            app = get_process_app()
            with app.app_context():
                # Build COMPACT prompt (800 chars) - for INSTANT greeting
                compact_prompt = build_compact_greeting_prompt(business_id, call_direction="inbound")
                stream_registry.set_metadata(call_sid, '_prebuilt_compact_prompt', compact_prompt)
                
                # Build FULL BUSINESS prompt (business-only) - for post-greeting injection
                # IMPORTANT: Never store/send global system rules inside this "full" prompt.
                full_prompt = build_full_business_prompt(business_id, call_direction="inbound")
                stream_registry.set_metadata(call_sid, '_prebuilt_full_prompt', full_prompt)
                
                # Avoid noisy stdout in production (can spike I/O/CPU under load).
                logger.debug("[PROMPT] Pre-built inbound prompts: compact_len=%s full_len=%s", len(compact_prompt), len(full_prompt))
        except Exception as e:
            logger.debug(f"[PROMPT] Background inbound prompt build failed (fallback to async build): {e}")
    
    # Start prompt building in background (non-blocking)
    if business_id and call_sid:
        threading.Thread(
            target=_prebuild_prompts_async,
            args=(call_sid, business_id),
            daemon=True,
            name=f"PromptBuild-{call_sid[:8]}"
        ).start()
    
    # 🎙️ NEW: Start recording from second 0 (background, non-blocking)
    # Recording will capture the ENTIRE call including AI greeting
    if call_sid:
        threading.Thread(
            target=_start_recording_from_second_zero,
            args=(call_sid, from_number, to_number),
            daemon=True,
            name=f"RecordingStart-{call_sid[:8]}"
        ).start()
    
    # === יצירה אוטומטית של ליד (ברקע) - Non-blocking ===
    # 🔥 GREETING OPTIMIZATION: Lead creation happens in background - doesn't block TwiML response
    if from_number:
        threading.Thread(
            target=_create_lead_from_call,
            args=(call_sid, from_number, to_number, business_id),
            daemon=True,
            name=f"LeadCreation-{call_sid[:8]}"
        ).start()
    
    # ⏱️ מדידה
    t1 = time.time()
    twiml_ms = int((t1 - t0) * 1000)
    
    # 🔥 GREETING PROFILER: Save TwiML ready timestamp for timeline analysis
    if call_sid:
        stream_registry.set_metric(call_sid, 'twiml_ready_ts', t1)
    
    # 🔥 GREETING SLA: Assert TwiML generation is fast enough
    if twiml_ms > 200:
        logger.warning(f"[SLA] TwiML generation too slow: {twiml_ms}ms > 200ms for {call_sid[:16]}")
    
    logger.info(f"[GREETING_PROFILER] incoming_call TwiML ready in {twiml_ms}ms")
    
    status_emoji = "✅" if twiml_ms < 200 else "⚠️"
    print(f"{status_emoji} incoming_call: {twiml_ms}ms - {call_sid[:16]}")
    
    # 🔥 DEBUG: Log exact TwiML being sent
    twiml_str = str(vr)
    print(f"🔥 TWIML_HOST={host}")
    print(f"🔥 TWIML_WS=wss://{host}/ws/twilio-media")
    print(f"🔥 TWIML_FULL={twiml_str[:500]}")
    
    return _twiml(vr)

@csrf.exempt
@twilio_bp.route("/webhook/outbound_call", methods=["POST", "GET"])
@require_twilio_signature
def outbound_call():
    """
    🔥 COST OPTIMIZATION: Outbound AI calls with conditional Media Stream
    
    Flow:
    1. Initial TwiML: Brief greeting/pause (NO expensive Media Stream yet)
    2. Wait for AMD callback (DetectMessageEnd - 2-4 seconds)
    3. If human answered: Upgrade call to add Media Stream (AI conversation)
    4. If voicemail: Hang up immediately (save 30-50% cost)
    5. If AMD uncertain/timeout: Fallback to upgrade (better safe than sorry)
    
    IMPORTANT: This prevents starting expensive Media Stream + Realtime API for:
    - Voicemail/answering machines (biggest savings!)
    - No-answer calls
    - Busy signals
    - Failed calls
    
    Note: AMD itself has a cost, so this optimization is most effective for
    high no-answer/voicemail rates (campaigns/lists). For calls with high
    answer rates, the AMD cost may offset some savings.
    """
    t0 = time.time()
    logger.info(f"[COST_OPT] outbound_call START at {t0}")
    
    if request.method == "GET":
        call_sid = request.args.get("CallSid", "")
        lead_id = request.args.get("lead_id", "")
        lead_name = request.args.get("lead_name", "")
        business_id = request.args.get("business_id", "")
        business_name = request.args.get("business_name", "")
        template_id = request.args.get("template_id", "")
    else:
        call_sid = request.form.get("CallSid", "")
        lead_id = request.args.get("lead_id", "")
        lead_name = request.args.get("lead_name", "")
        business_id = request.args.get("business_id", "")
        business_name = request.args.get("business_name", "")
        template_id = request.args.get("template_id", "")
    
    from_number = request.form.get("From", "") or request.args.get("From", "")
    to_number = request.form.get("To", "") or request.args.get("To", "")
    
    logger.info(f"📞 OUTBOUND_CALL webhook: call_sid={call_sid}, lead={lead_name}, template={template_id}")
    
    # 🔥 GUARD: Check if Stream already started (prevent duplicate)
    from server.stream_state import stream_registry
    if call_sid and stream_registry.get_metadata(call_sid, '_stream_started'):
        logger.warning(f"💰 [COST_OPT] Stream already started for {call_sid} - preventing duplicate")
        # Return empty response to prevent re-initialization
        vr = VoiceResponse()
        vr.pause(length=1)
        return _twiml(vr)
    
    # 🔥 COST OPTIMIZATION: Store outbound call metadata for AMD upgrade
    # This will be used by amd_status webhook to add Media Stream if human answers
    if call_sid and business_id:
        stream_registry.set_metadata(call_sid, '_outbound_lead_id', lead_id)
        stream_registry.set_metadata(call_sid, '_outbound_lead_name', lead_name)
        stream_registry.set_metadata(call_sid, '_outbound_business_id', business_id)
        stream_registry.set_metadata(call_sid, '_outbound_business_name', business_name)
        stream_registry.set_metadata(call_sid, '_outbound_template_id', template_id)
        stream_registry.set_metadata(call_sid, '_outbound_to_number', to_number)
        stream_registry.set_metadata(call_sid, '_outbound_from_number', from_number)
    
    if call_sid:
        try:
            existing = CallLog.query.filter_by(call_sid=call_sid).first()
            if existing:
                existing.status = "in_progress"
                existing.call_status = "in-progress"
                db.session.commit()
                logger.info(f"✅ Updated outbound call_log for {call_sid}")
        except Exception as e:
            logger.error(f"⚠️ Failed to update outbound call_log: {e}")
            db.session.rollback()
    
    public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
    if public_host:
        host = public_host
    else:
        host = (
            request.headers.get("X-Forwarded-Host") or 
            os.environ.get('REPLIT_DEV_DOMAIN') or 
            os.environ.get('REPLIT_DOMAINS', '').split(',')[0] or 
            request.host
        ).split(",")[0].strip()
    
    # 🔥 COST OPTIMIZATION: Initial TwiML with brief greeting, NO Media Stream
    # Play a short sound/pause to avoid awkward silence while waiting for AMD
    vr = VoiceResponse()
    
    # Brief "רגע אחד..." to acknowledge the call (not AI, just TTS)
    # This prevents awkward silence while AMD is detecting
    vr.say("רגע אחד", language="he-IL", voice="Google.he-IL-Wavenet-C")
    
    # Pause for AMD detection (2-4 seconds)
    vr.pause(length=3)
    
    # 🔥 FALLBACK: If AMD doesn't callback or is uncertain, redirect to upgrade
    # This ensures we don't lose customers due to AMD failure
    vr.redirect(f"https://{host}/webhook/outbound_call_upgrade?call_sid={call_sid}&business_id={business_id}&lead_id={lead_id}&lead_name={lead_name}&template_id={template_id}")
    
    # 🎙️ IMPORTANT: Recording will be started by AMD callback after "answered"
    # Don't start recording here - call might not connect yet (ringing/no-answer)
    
    t1 = time.time()
    twiml_ms = int((t1 - t0) * 1000)
    
    logger.info(f"[COST_OPT] outbound_call initial TwiML (NO Stream): {twiml_ms}ms - {call_sid[:16] if call_sid else 'N/A'}")
    
    return _twiml(vr)


@csrf.exempt
@twilio_bp.route("/webhook/stream_ended", methods=["POST"])
@require_twilio_signature
def stream_ended():
    """Stream ended - trigger recording + fast response"""
    # 🔥 VERIFICATION #2: Extract call_sid with fallback for different formats
    call_sid = request.form.get('CallSid') or request.form.get('callSid', '')
    stream_sid = request.form.get('StreamSid') or request.form.get('streamSid', '')
    
    # Log for debugging
    if not call_sid:
        print(f"⚠️ [STREAM_ENDED] No CallSid in request - stream_sid={stream_sid}, form_keys={list(request.form.keys())}")
    
    # 🔥 VERIFICATION #1: Close handler from webhook
    if call_sid:
        from server.media_ws_ai import close_handler_from_webhook
        close_handler_from_webhook(call_sid, "webhook_stream_ended")
    
    # החזרה מיידית
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store"
    
    # 🎧 CRITICAL LOG: Recording starts AFTER stream ends (after AI greeting finished)
    if call_sid:
        print(f"[RECORDING] Stream ended → safe to start recording for {call_sid}")
        threading.Thread(
            target=_trigger_recording_for_call, 
            args=(call_sid,), 
            daemon=True
        ).start()
        
    try:
        status = request.form.get('Status', 'N/A')
        print(f"STREAM_ENDED call={call_sid or 'N/A'} stream={stream_sid or 'N/A'} status={status}")
    except:
        pass
        
    return resp

@csrf.exempt
@twilio_bp.route("/webhook/outbound_call_upgrade", methods=["POST", "GET"])
@require_twilio_signature
def outbound_call_upgrade():
    """
    🔥 COST OPTIMIZATION: Upgrade outbound call to add Media Stream
    
    Called when:
    1. AMD detects human answered (from amd_status webhook)
    2. Fallback after pause timeout (if AMD didn't callback or uncertain)
    
    This adds the expensive Media Stream ONLY for answered calls,
    saving 30-50% cost on voicemail/no-answer calls.
    
    IMPORTANT: Sets guard flag to prevent duplicate Stream initialization.
    """
    # Get parameters from query string OR form data
    call_sid = request.args.get("call_sid") or request.form.get("CallSid", "")
    business_id = request.args.get("business_id") or request.form.get("business_id", "")
    lead_id = request.args.get("lead_id") or request.form.get("lead_id", "")
    lead_name = request.args.get("lead_name") or request.form.get("lead_name", "")
    template_id = request.args.get("template_id") or request.form.get("template_id", "")
    
    # Try to get from stream registry if not in params
    from server.stream_state import stream_registry
    if call_sid and not business_id:
        business_id = stream_registry.get_metadata(call_sid, '_outbound_business_id')
        lead_id = stream_registry.get_metadata(call_sid, '_outbound_lead_id')
        lead_name = stream_registry.get_metadata(call_sid, '_outbound_lead_name')
        template_id = stream_registry.get_metadata(call_sid, '_outbound_template_id')
    
    # 🔥 GUARD: Check if Stream already started (prevent duplicate)
    if call_sid and stream_registry.get_metadata(call_sid, '_stream_started'):
        logger.warning(f"💰 [COST_OPT] Stream already started for {call_sid} - preventing duplicate upgrade")
        # Return empty pause to prevent issues
        vr = VoiceResponse()
        vr.pause(length=1)
        return _twiml(vr)
    
    # 🔥 GUARD: Mark Stream as started (idempotent)
    if call_sid:
        stream_registry.set_metadata(call_sid, '_stream_started', True)
    
    logger.info(f"💰 [COST_OPT] outbound_call_upgrade: call_sid={call_sid}, business_id={business_id}")
    
    public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
    if public_host:
        host = public_host
    else:
        host = (
            request.headers.get("X-Forwarded-Host") or 
            os.environ.get('REPLIT_DEV_DOMAIN') or 
            os.environ.get('REPLIT_DOMAINS', '').split(',')[0] or 
            request.host
        ).split(",")[0].strip()
    
    # Get to/from numbers from registry
    to_number = stream_registry.get_metadata(call_sid, '_outbound_to_number') or "unknown"
    from_number = stream_registry.get_metadata(call_sid, '_outbound_from_number') or "unknown"
    
    # 🎙️ CRITICAL: Start recording NOW (call is answered and active)
    # Recording starts AFTER call is confirmed answered (not during ringing)
    if call_sid:
        threading.Thread(
            target=_start_recording_from_second_zero,
            args=(call_sid, from_number, to_number),
            daemon=True,
            name=f"RecordingStart-{call_sid[:8]}"
        ).start()
        logger.info(f"🎙️ [COST_OPT] Recording started for answered call: {call_sid}")
    
    # NOW add the Media Stream (expensive part)
    vr = VoiceResponse()
    
    connect = vr.connect(action=f"https://{host}/webhook/stream_ended")
    stream = connect.stream(
        url=f"wss://{host}/ws/twilio-media",
        track="inbound_track"
    )
    
    stream.parameter(name="CallSid", value=call_sid)
    stream.parameter(name="To", value=to_number)
    stream.parameter(name="direction", value="outbound")
    stream.parameter(name="lead_id", value=lead_id or "")
    stream.parameter(name="lead_name", value=lead_name or "")
    stream.parameter(name="business_id", value=business_id or "")
    if template_id:
        stream.parameter(name="template_id", value=template_id)
    
    # Pre-build prompts in background (same as before)
    def _prebuild_prompts_async_outbound(call_sid, business_id):
        """Background thread to pre-build outbound prompts"""
        try:
            from server.services.realtime_prompt_builder import (
                build_compact_greeting_prompt,
                build_full_business_prompt,
            )
            from server.stream_state import stream_registry
            from server.app_factory import get_process_app
            
            app = get_process_app()
            with app.app_context():
                compact_prompt = build_compact_greeting_prompt(int(business_id), call_direction="outbound")
                stream_registry.set_metadata(call_sid, '_prebuilt_compact_prompt', compact_prompt)
                
                full_prompt = build_full_business_prompt(int(business_id), call_direction="outbound")
                stream_registry.set_metadata(call_sid, '_prebuilt_full_prompt', full_prompt)
                
                logger.debug("[PROMPT] Pre-built outbound prompts: compact_len=%s full_len=%s", len(compact_prompt), len(full_prompt))
        except Exception as e:
            logger.debug(f"[PROMPT] Background outbound prompt build failed: {e}")
    
    if business_id and call_sid:
        threading.Thread(
            target=_prebuild_prompts_async_outbound,
            args=(call_sid, business_id),
            daemon=True,
            name=f"PromptBuildOut-{call_sid[:8]}"
        ).start()
    
    logger.info(f"💰 [COST_OPT] Media Stream added for human-answered call: {call_sid[:16]}")
    
    return _twiml(vr)

@csrf.exempt
@twilio_bp.route("/webhook/handle_recording", methods=["POST"])
@require_twilio_signature
def handle_recording():
    """
    ✅ BUILD 89: Handle recording webhook עם self-heal fallback
    שלב 4: שדרוג למענה מיידי עם monitoring משופר
    🔥 FIX: Capture Direction and ParentCallSid from webhook
    """
    import time
    start_time = time.time()
    
    # Immediate response preparation FIRST (before any processing)
    resp = make_response("", 200)
    resp.headers.update({
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Connection": "close"
    })
    
    # Fast data extraction
    call_sid = request.form.get("CallSid", "unknown")
    rec_url = request.form.get("RecordingUrl")
    rec_sid = request.form.get("RecordingSid")  # 🔥 FIX: Extract recording SID
    rec_duration = request.form.get("RecordingDuration", "0")
    rec_status = request.form.get("RecordingStatus", "unknown")
    
    # 🔥 NEW: Capture direction and parent_call_sid from recording webhook
    twilio_direction = request.form.get("Direction")
    parent_call_sid = request.form.get("ParentCallSid")
    from_number = request.form.get("From", "unknown")
    to_number = request.form.get("To", "unknown")
    
    # ✅ BUILD 89: עדכן או צור call_log מיד
    if call_sid and call_sid != "unknown":
        try:
            from server.tasks_recording import normalize_call_direction
            
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if not call_log:
                # Self-heal: צור fallback call_log
                print(f"⚠️ handle_recording: Creating fallback call_log for {call_sid}")
                # ✅ BUILD 155: שימוש בעסק פעיל ראשון + טלפון דינמי (אין fallback ל-1)
                from server.models_sql import Business
                biz = Business.query.filter_by(is_active=True).first()
                if not biz:
                    print(f"❌ No active business - cannot create fallback call_log")
                    return resp  # Return without creating orphan record
                biz_id = biz.id
                biz_phone = biz.phone_e164 or "unknown"
                print(f"📊 handle_recording fallback: business_id={biz_id}")
                
                # 🔥 NEW: Normalize direction when creating fallback
                normalized_direction = normalize_call_direction(twilio_direction) if twilio_direction else "inbound"
                
                call_log = CallLog(
                    call_sid=call_sid,
                    parent_call_sid=parent_call_sid,  # 🔥 NEW: Store parent call SID
                    from_number=from_number,
                    to_number=to_number,
                    business_id=biz_id,
                    direction=normalized_direction,  # 🔥 NEW: Normalized direction
                    twilio_direction=twilio_direction,  # 🔥 NEW: Original Twilio direction
                    call_status="completed",  # ✅ BUILD 90: Legacy field
                    status="recorded"
                )
                db.session.add(call_log)
            else:
                call_log.status = "recorded"
                
                # 🔥 CRITICAL: Smart direction update - allow upgrading from "unknown" to real value
                if twilio_direction:
                    # Update if: (1) never set, OR (2) currently "unknown"
                    if not call_log.twilio_direction or call_log.direction == "unknown":
                        call_log.twilio_direction = twilio_direction
                        call_log.direction = normalize_call_direction(twilio_direction)
                
                # 🔥 NEW: Update parent_call_sid if not set and available
                if parent_call_sid and not call_log.parent_call_sid:
                    call_log.parent_call_sid = parent_call_sid
                
                # Update from/to if they were "unknown" in initial creation
                if from_number and from_number != "unknown" and call_log.from_number == "unknown":
                    call_log.from_number = from_number
                if to_number and to_number != "unknown" and call_log.to_number == "unknown":
                    call_log.to_number = to_number
            
            # 🔥 FIX: עדכן recording_url AND recording_sid
            if rec_url:
                call_log.recording_url = rec_url
            if rec_sid:
                call_log.recording_sid = rec_sid
                print(f"✅ handle_recording: Saved recording_sid {rec_sid} for {call_sid}")
            
            db.session.commit()
            print(f"✅ handle_recording: Updated call_log for {call_sid} (direction={call_log.direction}, parent={parent_call_sid})")
        except Exception as e:
            print(f"⚠️ handle_recording DB error: {e}")
            db.session.rollback()
    
    # TRUE non-blocking background processing with daemon thread
    if rec_url and rec_url.strip():
        try:
            # Truly async - starts thread and returns immediately
            form_copy = dict(request.form)
            
            def async_enqueue():
                """Background thread for recording processing"""
                try:
                    enqueue_recording(form_copy)
                    print(f"✅ REC_QUEUED_ASYNC: {call_sid[:16]} duration={rec_duration}")
                except Exception as e:
                    print(f"❌ REC_QUEUE_ASYNC_FAIL: {call_sid[:16]} error={type(e).__name__}: {e}")
            
            # Fire daemon thread and return immediately (non-blocking)
            threading.Thread(target=async_enqueue, daemon=True).start()
            
            # Immediate success log (thread started, not completed)
            current_app.logger.info("REC_THREAD_STARTED", extra={
                "call_sid": call_sid[:16],
                "processing_ms": int((time.time() - start_time) * 1000)
            })
            
        except Exception as e:
            # Thread creation failed - ultra-fast error log
            current_app.logger.error("REC_THREAD_FAIL", extra={
                "call_sid": call_sid[:16],
                "error_type": type(e).__name__,
                "processing_ms": int((time.time() - start_time) * 1000)
            })
    else:
        # Log missing recording URL
        current_app.logger.warning("REC_NO_URL", extra={
            "call_sid": call_sid[:16],
            "status": rec_status,
            "processing_ms": int((time.time() - start_time) * 1000)
        })
    
    return resp

@csrf.exempt
@twilio_bp.route("/webhook/recording_status", methods=["POST"])
@require_twilio_signature
def recording_status():
    """
    🔥 NEW: Recording Status Callback - handles recording lifecycle events
    Called by Twilio when recording completes.
    
    This webhook receives:
    - RecordingStatus: 'completed' when recording is done
    - RecordingSid: Unique identifier for the recording
    - RecordingUrl: URL to download the recording
    - CallSid: The call this recording belongs to
    - RecordingDuration: Duration in seconds
    """
    import time
    start_time = time.time()
    
    # Immediate response preparation (Twilio expects fast ACK)
    resp = make_response("", 200)
    resp.headers.update({
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Connection": "close"
    })
    
    # Extract webhook data
    recording_status_value = request.form.get("RecordingStatus", "unknown")
    recording_sid = request.form.get("RecordingSid", "")
    recording_url = request.form.get("RecordingUrl", "")
    call_sid = request.form.get("CallSid", "")
    recording_duration = request.form.get("RecordingDuration", "0")
    from_number = request.form.get("From", "")
    to_number = request.form.get("To", "")
    
    print(f"🎙️ [REC_CB] recording_sid={recording_sid} call_sid={call_sid} status={recording_status_value} duration={recording_duration}s")
    logger.info(f"[REC_CB] recording_sid={recording_sid} call_sid={call_sid} status={recording_status_value} duration={recording_duration}s")
    
    # Only process completed recordings
    if recording_status_value == "completed":
        print(f"✅ [REC_CB] COMPLETED call_sid={call_sid} recording_sid={recording_sid} duration={recording_duration}s")
        
        # Update CallLog with recording information
        if call_sid:
            try:
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                
                if call_log:
                    # Update recording metadata
                    call_log.recording_url = recording_url
                    call_log.recording_sid = recording_sid
                    call_log.status = "recorded"
                    
                    # Save duration if not already set
                    if recording_duration and recording_duration != "0":
                        try:
                            duration_int = int(recording_duration)
                            if call_log.duration == 0 or call_log.duration is None:
                                call_log.duration = duration_int
                        except ValueError:
                            pass
                    
                    db.session.commit()
                    print(f"✅ [REC_CB] Updated CallLog: recording_url saved, status=recorded, duration={recording_duration}s")
                    logger.info(f"[REC_CB] Updated CallLog call_sid={call_sid} duration={recording_duration}s")
                    
                    # 🔥 CRITICAL: Trigger transcription job
                    # Use enqueue_recording_job for proper retry logic
                    from server.tasks_recording import enqueue_recording_job
                    
                    try:
                        business_id = call_log.business_id
                        
                        # Enqueue for background processing
                        enqueue_recording_job(
                            call_sid=call_sid,
                            recording_url=recording_url,
                            business_id=business_id,
                            from_number=from_number or call_log.from_number,
                            to_number=to_number or call_log.to_number,
                            retry_count=0
                        )
                        
                        print(f"✅ [REC_CB] Transcription job enqueued call_sid={call_sid}")
                        logger.info(f"[REC_CB] Transcription job enqueued call_sid={call_sid}")
                        
                    except Exception as e:
                        print(f"⚠️ [REC_CB] Failed to enqueue transcription: {e}")
                        logger.error(f"[REC_CB] Failed to enqueue transcription call_sid={call_sid}: {e}")
                    
                else:
                    print(f"⚠️ [REC_CB] CallLog not found call_sid={call_sid}")
                    logger.warning(f"[REC_CB] CallLog not found call_sid={call_sid}")
                    
            except Exception as e:
                print(f"❌ [REC_CB] Database error: {e}")
                logger.error(f"[REC_CB] Database error call_sid={call_sid}: {e}")
                db.session.rollback()
        else:
            print(f"⚠️ [REC_CB] No CallSid in webhook")
            logger.warning(f"[REC_CB] No CallSid in recording_status webhook")
    
    else:
        print(f"ℹ️ [REC_CB] Status '{recording_status_value}' call_sid={call_sid} - waiting for completion")
        logger.info(f"[REC_CB] Non-completed status '{recording_status_value}' call_sid={call_sid}")
    
    processing_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[REC_STATUS] Processed in {processing_ms}ms")
    
    return resp

@csrf.exempt
@twilio_bp.route("/webhook/stream_status", methods=["POST"])  
@require_twilio_signature
def stream_status():
    """
    ✅ BUILD 89: Stream status עם self-heal fallback
    עדכן call_log ב-DB, ואם לא קיים - צור fallback
    🔥 FIX: Capture Direction and ParentCallSid from webhook
    """
    try:
        call_sid = request.form.get('CallSid', 'N/A')
        stream_sid = request.form.get('StreamSid', 'N/A')
        event = request.form.get('Status', 'N/A')
        
        # 🔥 NEW: Capture direction and parent_call_sid
        twilio_direction = request.form.get('Direction')
        parent_call_sid = request.form.get('ParentCallSid')
        from_number = request.form.get('From', 'unknown')
        to_number = request.form.get('To', 'unknown')
        
        print(f"STREAM_STATUS call={call_sid} stream={stream_sid} event={event} direction={twilio_direction}")
        
        # ✅ BUILD 89: עדכן או צור call_log
        if call_sid and call_sid != 'N/A':
            try:
                from server.tasks_recording import normalize_call_direction
                
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                if not call_log:
                    # Self-heal: צור fallback call_log
                    print(f"⚠️ stream_status: Creating fallback call_log for {call_sid}")
                    # ✅ BUILD 155: שימוש בעסק פעיל ראשון + טלפון דינמי (אין fallback ל-1)
                    from server.models_sql import Business
                    biz = Business.query.filter_by(is_active=True).first()
                    if not biz:
                        print(f"❌ No active business - cannot create fallback call_log")
                        return make_response("", 200)  # Return without creating orphan record
                    biz_id = biz.id
                    biz_phone = biz.phone_e164 or "unknown"
                    print(f"📊 stream_status fallback: business_id={biz_id}")
                    
                    # 🔥 NEW: Normalize direction when creating fallback
                    normalized_direction = normalize_call_direction(twilio_direction) if twilio_direction else "inbound"
                    
                    call_log = CallLog(
                        call_sid=call_sid,
                        parent_call_sid=parent_call_sid,  # 🔥 NEW: Store parent call SID
                        from_number=from_number,
                        to_number=to_number,
                        business_id=biz_id,
                        direction=normalized_direction,  # 🔥 NEW: Normalized direction
                        twilio_direction=twilio_direction,  # 🔥 NEW: Original Twilio direction
                        call_status="in-progress",  # ✅ BUILD 90: Legacy field
                        status="streaming"
                    )
                    db.session.add(call_log)
                else:
                    # עדכן סטטוס
                    call_log.status = event if event != 'N/A' else "streaming"
                    
                    # 🔥 CRITICAL: Smart direction update - allow upgrading from "unknown" to real value
                    if twilio_direction:
                        # Update if: (1) never set, OR (2) currently "unknown"
                        if not call_log.twilio_direction or call_log.direction == "unknown":
                            call_log.twilio_direction = twilio_direction
                            call_log.direction = normalize_call_direction(twilio_direction)
                    
                    # 🔥 NEW: Update parent_call_sid if not set and available
                    if parent_call_sid and not call_log.parent_call_sid:
                        call_log.parent_call_sid = parent_call_sid
                    
                    # Update from/to if they were "unknown" in initial creation
                    if from_number and from_number != "unknown" and call_log.from_number == "unknown":
                        call_log.from_number = from_number
                    if to_number and to_number != "unknown" and call_log.to_number == "unknown":
                        call_log.to_number = to_number
                
                db.session.commit()
                print(f"✅ stream_status: Updated call_log for {call_sid}")
            except Exception as e:
                print(f"⚠️ stream_status DB error: {e}")
                db.session.rollback()
        
        # החזרה מיידית
        resp = make_response("", 200)
        resp.headers["Cache-Control"] = "no-store"
        return resp
        
    except Exception as e:
        print(f"❌ stream_status error: {e}")
        import traceback
        traceback.print_exc()
        return make_response("", 200)

@csrf.exempt
@twilio_bp.route("/webhook/call_status", methods=["POST", "GET"])
@require_twilio_signature
def call_status():
    """Handle call status updates - FAST אסינכרוני - BUILD 106
    
    Now extracts parent_call_sid and original Twilio direction to prevent duplicates
    and correctly classify call direction.
    """
    # BUILD 168.4: Support both POST (form) and GET (args)
    if request.method == "GET":
        call_sid = request.args.get("CallSid")
        call_status_val = request.args.get("CallStatus")
        call_duration = request.args.get("CallDuration", "0")
        twilio_direction = request.args.get("Direction")  # 🔥 FIX: No default - None if missing
        parent_call_sid = request.args.get("ParentCallSid")  # 🔥 NEW: Extract parent call SID
    else:
        call_sid = request.form.get("CallSid")
        call_status_val = request.form.get("CallStatus")
        call_duration = request.form.get("CallDuration", "0")
        twilio_direction = request.form.get("Direction")  # 🔥 FIX: No default - None if missing
        parent_call_sid = request.form.get("ParentCallSid")  # 🔥 NEW: Extract parent call SID
    
    # החזרה מיידית ללא עיכובים
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    
    # עיבוד ברקע אחרי שהחזרנו response
    try:
        current_app.logger.info("CALL_STATUS", extra={
            "call_sid": call_sid, 
            "status": call_status_val, 
            "duration": call_duration,
            "twilio_direction": twilio_direction,
            "parent_call_sid": parent_call_sid
        })
        if call_status_val in ["completed", "busy", "no-answer", "failed", "canceled"]:
            # ✅ BUILD 106: Save with duration and direction
            # 🔥 NEW: Pass twilio_direction and parent_call_sid for proper tracking
            from server.tasks_recording import normalize_call_direction
            # 🔥 CRITICAL: Only normalize if we have a direction, otherwise keep existing
            normalized_direction = normalize_call_direction(twilio_direction) if twilio_direction else None
            save_call_status(call_sid, call_status_val, int(call_duration), 
                           normalized_direction, twilio_direction, parent_call_sid)
            
            # 🔥 NEW: Check if this call is part of a queue run and fill slots
            # This is the event-driven queue processing
            try:
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                if call_log:
                    # Check if there's an associated job in a bulk run
                    from server.models_sql import OutboundCallJob
                    job = OutboundCallJob.query.filter_by(call_log_id=call_log.id).first()
                    if job and job.status == "calling":
                        # Update job status
                        from datetime import datetime
                        job.status = "completed" if call_status_val == "completed" else "failed"
                        job.completed_at = datetime.utcnow()
                        if call_status_val != "completed":
                            job.error_message = f"Call ended with status: {call_status_val}"
                        
                        # Update run counts
                        from server.models_sql import OutboundCallRun
                        run = OutboundCallRun.query.get(job.run_id)
                        if run:
                            run.in_progress_count -= 1
                            if call_status_val == "completed":
                                run.completed_count += 1
                            else:
                                run.failed_count += 1
                            db.session.commit()
                            
                            # Fill available slots - this is the key part!
                            from server.routes_outbound import fill_queue_slots_for_job
                            import threading
                            threading.Thread(
                                target=fill_queue_slots_for_job,
                                args=(job.id,),
                                daemon=True,
                                name=f"FillSlots-{job.id}"
                            ).start()
                            log.info(f"✅ [QUEUE] Call completed for job {job.id}, filling slots")
                        else:
                            db.session.commit()
            except Exception as queue_err:
                log.warning(f"Queue slot fill error (non-critical): {queue_err}")
            
            # 🔥 VERIFICATION #1: Close handler from webhook for terminal statuses
            if call_sid:
                from server.media_ws_ai import close_handler_from_webhook
                close_handler_from_webhook(call_sid, f"webhook_call_status_{call_status_val}")
            
            # 🔥 CRITICAL FIX: Close WebSocket immediately on terminal call status
            # This prevents unnecessary Twilio charges from WebSocket staying open
            if call_sid:
                session = stream_registry.get(call_sid)
                if session:
                    print(f"🛑 [CALL_STATUS] Call {call_status_val} - triggering WebSocket close for {call_sid}")
                    # Mark session as ended to trigger cleanup
                    session['ended'] = True
                    session['end_reason'] = f'call_status_{call_status_val}'
    except Exception:
        current_app.logger.exception("CALL_STATUS_HANDLER_ERROR")
    
    return resp


@csrf.exempt
@twilio_bp.route("/webhook/amd_status", methods=["POST", "GET"])
@require_twilio_signature
def amd_status():
    """
    🔥 COST OPTIMIZATION: AMD (Answering Machine Detection) callback
    
    Twilio sends AnsweredBy for outbound calls when machineDetection is enabled.
    - If human answered → Upgrade call to add Media Stream (AI conversation)
    - If voicemail/fax → Hang up immediately (save 30-50% cost)
    
    This is the key cost-saving mechanism for outbound calls.
    """
    # Support both POST and GET to be resilient (Twilio normally POSTs)
    if request.method == "GET":
        call_sid = request.args.get("CallSid") or ""
        answered_by = request.args.get("AnsweredBy") or ""
    else:
        call_sid = request.form.get("CallSid") or ""
        answered_by = request.form.get("AnsweredBy") or ""

    # Fast response (Twilio retries on slow handlers)
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"

    try:
        logger.info("AMD_STATUS", extra={"call_sid": call_sid, "answered_by": answered_by})

        # Twilio AnsweredBy can be: human, machine_start, machine_end_beep, machine_end, fax, unknown, etc.
        machine_values = {"machine_start", "machine_end_beep", "machine_end", "fax"}
        is_machine = answered_by in machine_values
        is_human = answered_by == "human"

        # Update DB (best-effort)
        if call_sid:
            try:
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                if call_log:
                    # Store AMD result in status field
                    # Only update status if call is in early stages to avoid overwriting terminal statuses
                    if call_log.status in EARLY_STAGE_STATUSES:
                        if is_machine:
                            call_log.status = AMD_STATUS_VOICEMAIL
                        else:
                            call_log.status = AMD_STATUS_HUMAN
                        db.session.commit()
                    else:
                        logger.info("AMD_STATUS: Skipping status update - already in terminal status", extra={"call_sid": call_sid, "status": call_log.status})
            except Exception as db_err:
                logger.warning(f"AMD_STATUS db update failed: {db_err}")
                db.session.rollback()

        # 🔥 COST OPTIMIZATION: Upgrade call to add Stream if human answered
        # This is the key cost-saving mechanism - only start expensive AI for humans
        if is_human and call_sid:
            try:
                # 🔥 GUARD: Check if Stream already started (prevent duplicate)
                from server.stream_state import stream_registry
                if stream_registry.get_metadata(call_sid, '_stream_started'):
                    logger.info(f"💰 [COST_OPT] AMD_SKIP: Stream already started for {call_sid}")
                    return resp
                
                # Mark as starting (will be confirmed by upgrade endpoint)
                stream_registry.set_metadata(call_sid, '_amd_upgrade_triggered', True)
                
                account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
                auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
                if account_sid and auth_token:
                    # Get call metadata from registry
                    import urllib.parse
                    
                    business_id = stream_registry.get_metadata(call_sid, '_outbound_business_id')
                    lead_id = stream_registry.get_metadata(call_sid, '_outbound_lead_id')
                    lead_name = stream_registry.get_metadata(call_sid, '_outbound_lead_name')
                    template_id = stream_registry.get_metadata(call_sid, '_outbound_template_id')
                    
                    public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
                    # Handle empty REPLIT_DOMAINS gracefully
                    replit_domains = os.environ.get('REPLIT_DOMAINS', '')
                    replit_domain = replit_domains.split(',')[0] if replit_domains else ''
                    host = public_host or os.environ.get('REPLIT_DEV_DOMAIN') or replit_domain
                    
                    if host:
                        # Build upgrade URL with properly encoded parameters
                        upgrade_url = f"https://{host}/webhook/outbound_call_upgrade?call_sid={urllib.parse.quote(call_sid)}"
                        if business_id:
                            upgrade_url += f"&business_id={urllib.parse.quote(str(business_id))}"
                        if lead_id:
                            upgrade_url += f"&lead_id={urllib.parse.quote(str(lead_id))}"
                        if lead_name:
                            # URL-encode lead_name to handle special characters
                            upgrade_url += f"&lead_name={urllib.parse.quote(str(lead_name))}"
                        if template_id:
                            upgrade_url += f"&template_id={urllib.parse.quote(str(template_id))}"
                        
                        # Upgrade call to add Media Stream
                        client = Client(account_sid, auth_token)
                        try:
                            client.calls(call_sid).update(url=upgrade_url, method='POST')
                            logger.info(f"💰 [COST_OPT] AMD_UPGRADE: Human answered, adding Stream for {call_sid}")
                        except Exception as update_err:
                            # Distinguish between different failure modes
                            error_msg = str(update_err).lower()
                            if 'not found' in error_msg or 'invalid' in error_msg:
                                logger.warning(f"AMD_UPGRADE_FAIL: Invalid call_sid {call_sid}: {update_err}")
                            elif 'completed' in error_msg or 'ended' in error_msg:
                                logger.info(f"AMD_UPGRADE_SKIP: Call {call_sid} already ended: {update_err}")
                            else:
                                logger.error(f"AMD_UPGRADE_ERROR: Unexpected error for {call_sid}: {update_err}")
                    else:
                        logger.error(f"💰 [COST_OPT] AMD_UPGRADE: No host configured for {call_sid}")
            except Exception as upgrade_err:
                logger.error(f"AMD_UPGRADE_FAIL call_sid={call_sid}: {upgrade_err}")

        # Hang up immediately for voicemail/fax (same as before)
        if is_machine and call_sid:
            try:
                account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
                auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
                if account_sid and auth_token:
                    client = Client(account_sid, auth_token)
                    try:
                        client.calls(call_sid).update(status="completed")
                        logger.info(f"💰 [COST_OPT] AMD_HANGUP: Voicemail detected, hanging up {call_sid} (saved Stream cost)")
                    except Exception as hangup_err:
                        error_msg = str(hangup_err).lower()
                        if 'not found' in error_msg or 'invalid' in error_msg:
                            logger.warning(f"AMD_HANGUP_SKIP: Call {call_sid} not found: {hangup_err}")
                        elif 'completed' in error_msg or 'ended' in error_msg:
                            logger.info(f"AMD_HANGUP_SKIP: Call {call_sid} already ended: {hangup_err}")
                        else:
                            logger.error(f"AMD_HANGUP_ERROR: Unexpected error for {call_sid}: {hangup_err}")
            except Exception as hang_err:
                logger.error(f"AMD_HANGUP_FAIL call_sid={call_sid}: {hang_err}")
    except Exception:
        logger.exception("AMD_STATUS_HANDLER_ERROR")

    return resp

@csrf.exempt  # ✅ BUILD 155: Added CSRF exemption for test webhook
@twilio_bp.route("/webhook/test", methods=["POST", "GET"])
def test_webhook():
    """Test webhook endpoint"""
    return "TEST OK", 200

# ✅ BUILD 157: Debug route to verify POST method works
@csrf.exempt
@twilio_bp.route("/webhook/debug-method", methods=["GET", "POST"])
def debug_method():
    """Debug route to verify HTTP methods"""
    logger.info(f"[TWILIO DEBUG] method={request.method}, path={request.path}")
    return f"method={request.method}, path={request.path}", 200

# All health endpoints are handled by app_factory.py to avoid conflicts
@twilio_bp.route("/webhook/test_media_streams_1756667590", methods=["GET"])
def test_media_streams_new():
    """Test endpoint for Media Streams - no cache, no Play"""
    # תיקון: דינמי במקום hardcoded
    scheme = (request.headers.get("X-Forwarded-Proto") or "https").split(",")[0].strip()
    host   = (request.headers.get("X-Forwarded-Host")  or request.host).split(",")[0].strip()
    base   = f"{scheme}://{host}"
    call_sid = "TEST_NEW"
    
    # ✅ FIX Error 12100: NO leading spaces/whitespace in XML tags
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Response>',
        f'<Connect action="{base}/webhook/stream_ended">',
        f'<Stream url="wss://{host}/ws/twilio-media" statusCallback="{base}/webhook/stream_status">',
        f'<Parameter name="call_sid" value="{call_sid}"/>',
        '</Stream>',
        '</Connect>',
        '</Response>',
    ]
    twiml = "".join(parts)
    
    resp = make_response(twiml.encode("utf-8"), 200)
    resp.headers["Content-Type"] = "application/xml; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store, no-cache"
    return resp
