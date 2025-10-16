"""
Hebrew AI Call Center - Twilio Routes FIXED לפי ההנחיות המדויקות
שלב 4: שיחות → לידים + תמלול אוטומטי
Build 89: ImportError Fix + Immediate call_log Creation
"""
import os
import time
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

twilio_bp = Blueprint("twilio", __name__)

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
                    # ✅ FIX: Use correct MP3 URL construction
                    recording_mp3_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording.sid}.mp3"
                    form_data = {
                        'CallSid': call_sid,
                        'RecordingUrl': recording_mp3_url,
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
                # ✅ FIX: Prefer PUBLIC_HOST in production, then dev domain for local testing
                public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
                host = public_host or os.environ.get('REPLIT_DEV_DOMAIN') or os.environ.get('REPLIT_DOMAINS', '').split(',')[0] or 'your-app.replit.app'
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
    """
    from server.app_factory import create_app
    
    # ✅ ברירת מחדל ל-to_number
    if not to_number:
        to_number = "+97233763805"
    
    print(f"🔵 CREATE_LEAD_FROM_CALL - Starting for {from_number}, call_sid={call_sid}")
    
    try:
        # יצירת app context לthread
        app = create_app()
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
                        print(f"⚠️ Thread using fallback business_id={business_id}")
                    else:
                        biz = Business.query.first()
                        business_id = biz.id if biz else 1
                        print(f"⚠️ Thread using ultimate fallback business_id={business_id}")
            
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
                print(f"✅ CustomerIntelligence: customer_id={customer.id if customer else None}, lead_id={lead.id if lead else None}")
            except Exception as e:
                print(f"⚠️ CustomerIntelligence failed (non-critical): {e}")
            
            # ✅ שלב 3: עדכן call_log עם customer_id (אם נוצר)
            if call_log and customer:
                call_log.customer_id = customer.id
                call_log.status = "in_progress"
                db.session.commit()
                print(f"✅ Updated call_log with customer_id={customer.id}")
            
            # ✅ שלב 4: fallback lead אם CustomerIntelligence נכשל
            if not lead and customer:
                try:
                    lead = Lead()
                    lead.tenant_id = business_id
                    lead.phone_e164 = from_number
                    lead.source = "call"
                    lead.external_id = call_sid
                    lead.status = "new"
                    lead.notes = f"שיחה נכנסת - {call_sid}"
                    db.session.add(lead)
                    db.session.commit()
                    print(f"✅ Created fallback lead ID={lead.id}")
                except Exception as e:
                    print(f"⚠️ Fallback lead creation failed: {e}")
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
    
    # בנה host נכון
    public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
    replit_domain = public_host or os.environ.get('REPLIT_DEV_DOMAIN') or os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
    host = (request.headers.get("X-Forwarded-Host") or replit_domain or request.host).split(",")[0].strip()
    
    vr = VoiceResponse()
    connect = vr.connect(action=f"https://{host}/webhook/stream_ended")
    stream = connect.stream(
        url=f"wss://{host}/ws/twilio-media",
        status_callback=f"https://{host}/webhook/stream_status"
    )
    stream.parameter(name="CallSid", value=call_sid)
    stream.parameter(name="To", value="+97233763805")  # ✅ Fixed: correct number for business 1
    
    return _twiml(vr)

@csrf.exempt
@twilio_bp.route("/webhook/voice", methods=["POST"])
@require_twilio_signature
def voice_webhook():
    """
    ✅ BUILD 70: Main Twilio voice webhook - delegates to incoming_call
    This is the primary webhook URL configured in Twilio console
    """
    return incoming_call()

@csrf.exempt
@twilio_bp.route("/webhook/incoming_call", methods=["POST"])
@require_twilio_signature
def incoming_call():
    """
    ✅ BUILD 89: צור call_log מיד + TwiML with Twilio SDK + Parameter (CRITICAL!)
    """
    start_time = time.time()
    
    call_sid = request.form.get("CallSid", "")
    from_number = request.form.get("From", "")
    to_number = request.form.get("To", "")
    
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
            print(f"✅ Resolved business_id={business_id} from to_number={to_number} (Business: {business.name})")
        else:
            print(f"⚠️ No business found for to_number={to_number}")
            # Debug: show what we have
            all_businesses = Business.query.filter_by(is_active=True).all()
            print(f"📋 Active businesses: {[(b.id, b.name, b.phone_e164) for b in all_businesses]}")
    
    # Fallback: עסק פעיל ראשון
    if not business_id:
        business = Business.query.filter_by(is_active=True).first()
        if business:
            business_id = business.id
            print(f"⚠️ Using fallback business_id={business_id} (first active)")
        else:
            business = Business.query.first()
            business_id = business.id if business else 1
            print(f"⚠️ Using ultimate fallback business_id={business_id}")
    
    if call_sid and from_number:
        try:
            # בדוק אם כבר קיים (למקרה של retry)
            existing = CallLog.query.filter_by(call_sid=call_sid).first()
            if not existing:
                call_log = CallLog(
                    call_sid=call_sid,
                    from_number=from_number,
                    to_number=to_number or "+97233763805",
                    business_id=business_id,
                    call_status="initiated",  # ✅ BUILD 90: Legacy field
                    status="initiated"
                )
                db.session.add(call_log)
                db.session.commit()
                print(f"✅ call_log created immediately for {call_sid}")
            else:
                print(f"✅ call_log already exists for {call_sid}")
        except Exception as e:
            print(f"⚠️ Failed to create call_log immediately: {e}")
            db.session.rollback()
    
    # בנה host נכון (בלי https://)
    public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
    replit_domain = public_host or os.environ.get('REPLIT_DEV_DOMAIN') or os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
    host = (request.headers.get("X-Forwarded-Host") or replit_domain or request.host).split(",")[0].strip()
    
    # ✅ Twilio SDK
    vr = VoiceResponse()
    
    # ✅ Connect + Stream
    connect = vr.connect(action=f"https://{host}/webhook/stream_ended")
    stream = connect.stream(
        url=f"wss://{host}/ws/twilio-media",
        status_callback=f"https://{host}/webhook/stream_status"
    )
    
    # ✅ CRITICAL: הוסף Parameters עם CallSid + To (חובה!)
    stream.parameter(name="CallSid", value=call_sid)
    stream.parameter(name="To", value=to_number)  # ✅ CRITICAL: שלח To ל-WebSocket!
    
    # ✅ BUILD 90: Add Record fallback (if stream fails, recording still works!)
    vr.record(
        play_beep=False,
        timeout=4,
        max_length=300,
        transcribe=False,
        action=f"https://{host}/webhook/handle_recording"
    )
    
    # === יצירה אוטומטית של ליד (ברקע) ===
    if from_number:
        print(f"🟢 INCOMING_CALL - Starting thread to create lead for {from_number}, call_sid={call_sid}")
        threading.Thread(
            target=_create_lead_from_call,
            args=(call_sid, from_number, to_number, business_id),
            daemon=True,
            name=f"LeadCreation-{call_sid[:8]}"
        ).start()
        print(f"🟢 INCOMING_CALL - Thread started successfully")
    else:
        print(f"⚠️ INCOMING_CALL - No from_number, skipping lead creation")
    
    # ⏱️ מדידה
    response_time_ms = int((time.time() - start_time) * 1000)
    status_emoji = "✅" if response_time_ms < 1500 else "⚠️"
    print(f"{status_emoji} incoming_call: {response_time_ms}ms - {call_sid[:16]}")
    
    return _twiml(vr)

@csrf.exempt
@twilio_bp.route("/webhook/stream_ended", methods=["POST"])
@require_twilio_signature
def stream_ended():
    """Stream ended - trigger recording + fast response"""
    call_sid = request.form.get('CallSid', '')
    
    # החזרה מיידית
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store"
    
    # עיבוד ברקע - עורר הקלטה או חפש הקלטה קיימת
    if call_sid:
        threading.Thread(
            target=_trigger_recording_for_call, 
            args=(call_sid,), 
            daemon=True
        ).start()
        
    try:
        call_sid = request.form.get('CallSid', 'N/A')
        stream_sid = request.form.get('StreamSid', 'N/A') 
        status = request.form.get('Status', 'N/A')
        print(f"STREAM_ENDED call={call_sid} stream={stream_sid} status={status}")
    except:
        pass
        
    return resp

@csrf.exempt
@twilio_bp.route("/webhook/handle_recording", methods=["POST"])
@require_twilio_signature
def handle_recording():
    """
    ✅ BUILD 89: Handle recording webhook עם self-heal fallback
    שלב 4: שדרוג למענה מיידי עם monitoring משופר
    """
    import time
    start_time = time.time()
    
    # Fast data extraction
    call_sid = request.form.get("CallSid", "unknown")
    rec_url = request.form.get("RecordingUrl")
    rec_duration = request.form.get("RecordingDuration", "0")
    rec_status = request.form.get("RecordingStatus", "unknown")
    
    # ✅ BUILD 89: עדכן או צור call_log מיד
    if call_sid and call_sid != "unknown":
        try:
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if not call_log:
                # Self-heal: צור fallback call_log
                print(f"⚠️ handle_recording: Creating fallback call_log for {call_sid}")
                # ✅ BUILD 98: שימוש בעסק פעיל ראשון
                from server.models_sql import Business
                biz = Business.query.filter_by(is_active=True).first() or Business.query.first()
                biz_id = biz.id if biz else 1
                print(f"📊 handle_recording fallback: business_id={biz_id}")
                
                call_log = CallLog(
                    call_sid=call_sid,
                    from_number="unknown",
                    to_number="+97233763805",
                    business_id=biz_id,
                    call_status="completed",  # ✅ BUILD 90: Legacy field
                    status="recorded"
                )
                db.session.add(call_log)
            else:
                call_log.status = "recorded"
            
            # עדכן recording_url
            if rec_url:
                call_log.recording_url = rec_url
            
            db.session.commit()
            print(f"✅ handle_recording: Updated call_log for {call_sid}")
        except Exception as e:
            print(f"⚠️ handle_recording DB error: {e}")
            db.session.rollback()
    
    # Immediate response preparation (no blocking operations)
    resp = make_response("", 200)
    resp.headers.update({
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Connection": "close"
    })
    
    # TRUE non-blocking background processing with daemon thread
    if rec_url and rec_url.strip():
        try:
            # Truly async - starts thread and returns immediately
            form_copy = dict(request.form)
            
            def async_enqueue():
                """Background thread for recording processing"""
                try:
                    enqueue_recording(form_copy)
                    current_app.logger.info("REC_QUEUED_ASYNC", extra={
                        "call_sid": call_sid[:16],
                        "duration": rec_duration,
                        "status": rec_status
                    })
                except Exception as e:
                    current_app.logger.error("REC_QUEUE_ASYNC_FAIL", extra={
                        "call_sid": call_sid[:16],
                        "error_type": type(e).__name__
                    })
            
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
@twilio_bp.route("/webhook/stream_status", methods=["POST"])  
@require_twilio_signature
def stream_status():
    """
    ✅ BUILD 89: Stream status עם self-heal fallback
    עדכן call_log ב-DB, ואם לא קיים - צור fallback
    """
    try:
        call_sid = request.form.get('CallSid', 'N/A')
        stream_sid = request.form.get('StreamSid', 'N/A')
        event = request.form.get('Status', 'N/A')
        
        print(f"STREAM_STATUS call={call_sid} stream={stream_sid} event={event}")
        
        # ✅ BUILD 89: עדכן או צור call_log
        if call_sid and call_sid != 'N/A':
            try:
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                if not call_log:
                    # Self-heal: צור fallback call_log
                    print(f"⚠️ stream_status: Creating fallback call_log for {call_sid}")
                    # ✅ BUILD 98: שימוש בעסק פעיל ראשון
                    from server.models_sql import Business
                    biz = Business.query.filter_by(is_active=True).first() or Business.query.first()
                    biz_id = biz.id if biz else 1
                    print(f"📊 stream_status fallback: business_id={biz_id}")
                    
                    call_log = CallLog(
                        call_sid=call_sid,
                        from_number="unknown",
                        to_number="+97233763805",
                        business_id=biz_id,
                        call_status="in-progress",  # ✅ BUILD 90: Legacy field
                        status="streaming"
                    )
                    db.session.add(call_log)
                else:
                    # עדכן סטטוס
                    call_log.status = event if event != 'N/A' else "streaming"
                
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
@twilio_bp.route("/webhook/call_status", methods=["POST"])
@require_twilio_signature
def call_status():
    """Handle call status updates - FAST אסינכרוני"""
    call_sid = request.form.get("CallSid")
    call_status = request.form.get("CallStatus")
    
    # החזרה מיידית ללא עיכובים
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    
    # עיבוד ברקע אחרי שהחזרנו response
    try:
        current_app.logger.info("CALL_STATUS", extra={"call_sid": call_sid, "status": call_status})
        if call_status in ["completed", "busy", "no-answer", "failed", "canceled"]:
            save_call_status(call_sid, call_status)  # כעת אסינכרוני
    except Exception:
        current_app.logger.exception("CALL_STATUS_HANDLER_ERROR")
    
    return resp

@twilio_bp.route("/webhook/test", methods=["POST", "GET"])
def test_webhook():
    """Test webhook endpoint"""
    return "TEST OK", 200

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
