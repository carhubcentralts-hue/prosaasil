"""
BUILD 174: Outbound Calls API Routes
שיחות יוצאות - API להתחלת שיחות AI יוצאות ללידים

Endpoints:
- POST /api/outbound_calls/start - Start outbound calls to leads
- GET /api/outbound_calls/templates - Get outbound call templates
- GET /api/outbound_calls/counts - Get current active call counts
"""
import os
import re
import logging
from urllib.parse import quote  # 🔧 BUILD 177: URL encode Hebrew characters
from sqlalchemy import func
from flask import Blueprint, jsonify, request, g
from server.models_sql import db, CallLog, Lead, Business, OutboundCallTemplate, BusinessSettings
from server.auth_api import require_api_auth
from server.services.call_limiter import check_call_limits, get_call_counts, MAX_TOTAL_CALLS_PER_BUSINESS, MAX_OUTBOUND_CALLS_PER_BUSINESS
from twilio.rest import Client

log = logging.getLogger(__name__)

# ✅ Compile regex pattern once at module level for performance
STATUS_FILTER_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def normalize_israeli_phone(phone: str) -> str:
    """
    Normalize Israeli phone number to E.164 format (+972XXXXXXXXX)
    
    Handles:
    - +972XXXXXXXXX -> +972XXXXXXXXX (already E.164)
    - 972XXXXXXXXX -> +972XXXXXXXXX (missing +)
    - 0XXXXXXXXX -> +972XXXXXXXXX (local format)
    - 05XXXXXXXX -> +9725XXXXXXXX (mobile local)
    
    Returns the original string if it can't be normalized
    """
    if not phone:
        return phone
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone.strip())
    
    # Already in E.164 format with +972
    if cleaned.startswith('+972'):
        return cleaned
    
    # Has 972 prefix but missing +
    if cleaned.startswith('972') and len(cleaned) >= 12:
        return '+' + cleaned
    
    # Israeli local format (starts with 0)
    if cleaned.startswith('0') and len(cleaned) >= 10:
        # Remove leading 0 and add +972
        return '+972' + cleaned[1:]
    
    # If it already has a different country code (starts with +), keep it
    if cleaned.startswith('+'):
        return cleaned
    
    # Fallback: assume it's missing the leading 0 for Israeli mobile
    if len(cleaned) == 9 and cleaned[0] in '5':  # Israeli mobile without 0
        return '+972' + cleaned
    
    # Return original if we can't normalize
    log.warning(f"Could not normalize phone number: {phone}")
    return phone

outbound_bp = Blueprint("outbound", __name__)


def get_twilio_client():
    """Get Twilio REST client"""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    
    if not account_sid or not auth_token:
        raise ValueError("Missing Twilio credentials")
    
    return Client(account_sid, auth_token)


def get_business_phone(business_id: int) -> str | None:
    """Get the business phone number for outbound calls"""
    business = Business.query.get(business_id)
    if business and business.phone_e164:
        return business.phone_e164
    
    # 🔥 BUILD 186 FIX: Handle missing columns gracefully
    try:
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        if settings and settings.phone_number:
            return settings.phone_number
    except Exception as db_err:
        log.warning(f"⚠️ Could not load settings for {business_id} (DB schema issue): {db_err}")
    
    return None


def get_public_host() -> str:
    """Get public host for webhook URLs"""
    public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
    if public_host:
        return public_host
    
    return os.environ.get('REPLIT_DEV_DOMAIN') or os.environ.get('REPLIT_DOMAINS', '').split(',')[0] or 'localhost'


@outbound_bp.route("/api/outbound_calls/templates", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def get_outbound_templates():
    """
    Get outbound call templates for current business
    
    Returns list of active templates with their prompts
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    # For system_admin without tenant context, return empty list (they need to view a specific business)
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"templates": [], "message": "בחר עסק לצפייה בתבניות"})
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        templates = OutboundCallTemplate.query.filter_by(
            business_id=tenant_id,
            is_active=True
        ).order_by(OutboundCallTemplate.name).all()
        
        result = []
        for t in templates:
            result.append({
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "prompt_text": t.prompt_text,
                "greeting_template": t.greeting_template
            })
        
        return jsonify({"templates": result})
    
    except Exception as e:
        log.error(f"Error fetching templates: {e}")
        return jsonify({"error": "שגיאה בטעינת תבניות"}), 500


@outbound_bp.route("/api/outbound_calls/counts", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def get_call_counts_endpoint():
    """
    Get current active call counts for the business
    
    Returns:
        active_total: Total active calls
        active_outbound: Active outbound calls
        max_total: Maximum allowed total calls
        max_outbound: Maximum allowed outbound calls
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    # For system_admin without tenant context, return zero counts
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({
                "active_total": 0,
                "active_outbound": 0,
                "max_total": MAX_TOTAL_CALLS_PER_BUSINESS,
                "max_outbound": MAX_OUTBOUND_CALLS_PER_BUSINESS,
                "message": "בחר עסק לצפייה בשיחות פעילות"
            })
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        counts = get_call_counts(tenant_id)
        return jsonify(counts)
    except Exception as e:
        log.error(f"Error getting call counts: {e}")
        return jsonify({"error": "שגיאה בטעינת נתונים"}), 500


@outbound_bp.route("/api/outbound_calls/start", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def start_outbound_calls():
    """
    Start outbound AI calls to selected leads.
    Uses outbound_ai_prompt from business settings.
    
    Request body:
    {
        "lead_ids": [123, 456, 789]  // 1-3 leads
    }
    
    Returns:
    {
        "success": true,
        "calls": [
            {"lead_id": 123, "call_sid": "CA...", "status": "initiated"},
            ...
        ]
    }
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני הפעלת שיחות יוצאות"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "נתונים חסרים"}), 400
    
    lead_ids = data.get("lead_ids", [])
    
    if not lead_ids or not isinstance(lead_ids, list):
        return jsonify({"error": "יש לבחור לפחות ליד אחד"}), 400
    
    # ✅ REMOVED: 3-lead limit restriction. Now supports unlimited selections.
    # If more than 3 leads, the system automatically uses bulk queue mode.
    
    allowed, error_msg = check_call_limits(tenant_id, len(lead_ids))
    if not allowed:
        return jsonify({"error": error_msg}), 429
    
    try:
        leads = Lead.query.filter(
            Lead.id.in_(lead_ids),
            Lead.tenant_id == tenant_id
        ).all()
        
        if len(leads) != len(lead_ids):
            return jsonify({"error": "לא נמצאו כל הלידים שנבחרו"}), 404
        
        from_phone = get_business_phone(tenant_id)
        if not from_phone:
            return jsonify({"error": "מספר טלפון של העסק לא מוגדר"}), 400
        
        business = Business.query.get(tenant_id)
        business_name = business.name if business else "העסק"
        
        host = get_public_host()
        
        results = []
        
        for lead in leads:
            if not lead.phone_e164:
                results.append({
                    "lead_id": lead.id,
                    "lead_name": lead.full_name,
                    "status": "failed",
                    "error": "אין מספר טלפון לליד"
                })
                continue
            
            # Normalize phone number to E.164 format
            normalized_phone = normalize_israeli_phone(lead.phone_e164)
            log.info(f"📞 Phone normalization: {lead.phone_e164} -> {normalized_phone}")
            
            try:
                call_log = CallLog()
                call_log.business_id = tenant_id
                call_log.lead_id = lead.id
                call_log.from_number = from_phone
                call_log.to_number = normalized_phone  # Use normalized phone
                call_log.direction = "outbound"
                call_log.status = "initiated"
                call_log.call_status = "initiated"
                db.session.add(call_log)
                db.session.flush()
                
                lead_name = lead.full_name or "לקוח"
                
                # 🔧 BUILD 177: URL-encode Hebrew characters to prevent Twilio 400 errors
                webhook_url = f"https://{host}/webhook/outbound_call"
                webhook_url += f"?call_id={call_log.id}"
                webhook_url += f"&lead_id={lead.id}"
                webhook_url += f"&lead_name={quote(lead_name, safe='')}"
                webhook_url += f"&business_id={tenant_id}"
                webhook_url += f"&business_name={quote(business_name, safe='')}"
                
                client = get_twilio_client()
                
                # 🔥 FIX: Add recordingStatusCallback to ensure recordings are linked to leads
                # ✅ AMD: Correct parameters for Twilio Python SDK
                amd_callback_url = f"https://{host}/webhook/amd_status"
                
                try:
                    # Try with correct AMD parameters (async_amd + async_amd_status_callback)
                    twilio_call = client.calls.create(
                        to=normalized_phone,  # Use normalized phone
                        from_=from_phone,
                        url=webhook_url,
                        status_callback=f"https://{host}/webhook/call_status",
                        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                        # ✅ AMD: Correct Twilio Python SDK parameters
                        machine_detection="DetectMessageEnd",
                        async_amd=True,
                        async_amd_status_callback=amd_callback_url,
                        async_amd_status_callback_method="POST",
                        record=True,
                        recording_status_callback=f"https://{host}/webhook/handle_recording",
                        recording_status_callback_event=['completed']
                    )
                except TypeError as amd_error:
                    # Fallback: AMD parameters not supported by SDK version - create call without AMD
                    log.warning(f"AMD parameters not supported (SDK version issue): {amd_error}. Creating call without AMD.")
                    twilio_call = client.calls.create(
                        to=normalized_phone,
                        from_=from_phone,
                        url=webhook_url,
                        status_callback=f"https://{host}/webhook/call_status",
                        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                        record=True,
                        recording_status_callback=f"https://{host}/webhook/handle_recording",
                        recording_status_callback_event=['completed']
                    )
                    # Log warning but continue - call was created successfully
                    log.info(f"📞 Outbound call started WITHOUT AMD: lead={lead.id}, call_sid={twilio_call.sid}")
                
                call_log.call_sid = twilio_call.sid
                call_log.status = "ringing"
                call_log.call_status = "ringing"
                db.session.commit()
                
                log.info(f"📞 Outbound call started: lead={lead.id}, call_sid={twilio_call.sid}")
                
                results.append({
                    "lead_id": lead.id,
                    "lead_name": lead_name,
                    "call_sid": twilio_call.sid,
                    "status": "initiated"
                })
                
            except Exception as e:
                log.error(f"Failed to start call to lead {lead.id}: {e}")
                db.session.rollback()
                results.append({
                    "lead_id": lead.id,
                    "lead_name": lead.full_name,
                    "status": "failed",
                    "error": str(e)
                })
        
        successful_calls = [r for r in results if r.get("status") == "initiated"]
        
        return jsonify({
            "success": len(successful_calls) > 0,
            "message": f"הופעלו {len(successful_calls)} שיחות מתוך {len(lead_ids)}",
            "calls": results
        })
        
    except Exception as e:
        log.error(f"Error starting outbound calls: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": f"שגיאה בהפעלת השיחות: {str(e)}"}), 500


@outbound_bp.route("/api/outbound_calls/templates", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin'])
def create_outbound_template():
    """
    Create a new outbound call template
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני יצירת תבנית"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "נתונים חסרים"}), 400
    
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    prompt_text = data.get("prompt_text", "").strip()
    greeting_template = data.get("greeting_template", "").strip()
    
    if not name:
        return jsonify({"error": "שם התבנית חובה"}), 400
    
    if not prompt_text:
        return jsonify({"error": "הנחיות לשיחה חובה"}), 400
    
    try:
        template = OutboundCallTemplate()
        template.business_id = tenant_id
        template.name = name
        template.description = description
        template.prompt_text = prompt_text
        template.greeting_template = greeting_template
        template.is_active = True
        db.session.add(template)
        db.session.commit()
        
        log.info(f"✅ Created outbound template: id={template.id}, name={name}")
        
        return jsonify({
            "success": True,
            "template": {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "prompt_text": template.prompt_text,
                "greeting_template": template.greeting_template
            }
        }), 201
        
    except Exception as e:
        log.error(f"Error creating template: {e}")
        db.session.rollback()
        return jsonify({"error": "שגיאה ביצירת התבנית"}), 500


@outbound_bp.route("/api/outbound_calls/templates/<int:template_id>", methods=["DELETE"])
@require_api_auth(['system_admin', 'owner', 'admin'])
def delete_outbound_template(template_id: int):
    """
    Soft delete (deactivate) an outbound call template
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני מחיקת תבנית"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        template = OutboundCallTemplate.query.filter_by(
            id=template_id,
            business_id=tenant_id
        ).first()
        
        if not template:
            return jsonify({"error": "תבנית לא נמצאה"}), 404
        
        template.is_active = False
        db.session.commit()
        
        return jsonify({"success": True, "message": "התבנית נמחקה"})
        
    except Exception as e:
        log.error(f"Error deleting template: {e}")
        db.session.rollback()
        return jsonify({"error": "שגיאה במחיקת התבנית"}), 500


# ========================================================
# BUILD 182: Outbound Import Leads API
# ייבוא לידים מקובץ CSV לשיחות יוצאות
# ========================================================

MAX_IMPORTED_LEADS_PER_BUSINESS = 5000


@outbound_bp.route("/api/outbound/import-leads", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin'])
def import_outbound_leads():
    """
    BUILD 182: Import leads from CSV for outbound calls
    
    Accepts CSV/Excel/JSON and tries to auto-map columns. Only phone is required.
    Maximum 5000 leads per business total.
    
    Returns:
    {
        "success": true,
        "list_id": 123,
        "imported_count": 50,
        "skipped_count": 2,
        "errors_sample": ["שורה 3: טלפון לא תקין"],
        "mapping": {"phone": "טלפון", "name": "שם", "method": "header|content|fallback"}
    }
    """
    import csv
    import io
    from datetime import datetime
    from flask import session
    from server.models_sql import OutboundLeadList
    from typing import Any
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני ייבוא לידים"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        # Count existing imported leads for this business
        existing_count = Lead.query.filter_by(
            tenant_id=tenant_id,
            source="imported_outbound"
        ).count()

        # -----------------------------
        # Forgiving parsing + auto-mapping
        # -----------------------------
        header_synonyms = {
            "phone": [
                "phone", "phone_number", "mobile", "cell", "tel", "telephone",
                "טלפון", "נייד", "מספר", "מס טלפון", "מספר טלפון"
            ],
            "name": [
                "name", "full_name", "full name", "customer", "client",
                "שם", "שם מלא", "לקוח"
            ],
            "city": ["city", "address", "עיר", "כתובת"],
            "notes": ["notes", "comment", "comments", "remark", "הערות", "הערה"],
        }

        def _norm_header(h: str) -> str:
            return re.sub(r"\s+", " ", (h or "").strip().lower())

        def _looks_like_header_cell(cell: str) -> bool:
            c = (cell or "").strip()
            if not c:
                return False
            # headers are usually short and do not contain many digits
            digits = sum(ch.isdigit() for ch in c)
            letters = sum(ch.isalpha() for ch in c)
            return digits == 0 and (letters > 0 or len(c) <= 20)

        def _decode_bytes(raw: bytes) -> str:
            for enc in ("utf-8-sig", "utf-8", "cp1255", "iso-8859-8"):
                try:
                    return raw.decode(enc)
                except Exception:
                    continue
            # last resort
            return raw.decode("utf-8", errors="replace")

        def _strip_phone_chars(s: str) -> str:
            return re.sub(r"[^\d+]", "", (s or "").strip())

        def _normalize_phone_forgiving(raw_phone: str) -> str | None:
            """
            Forgiving phone normalization.
            Returns E.164-like string (e.g. +9725XXXXXXXX) or None if invalid.
            """
            if not raw_phone:
                return None

            cleaned = _strip_phone_chars(raw_phone)
            if not cleaned:
                return None

            # If starts with + and not Israeli, accept if it's plausibly E.164
            if cleaned.startswith("+") and not cleaned.startswith("+972"):
                digits_only = re.sub(r"\D", "", cleaned)
                if 10 <= len(digits_only) <= 15:
                    return cleaned  # keep as provided (+country...)
                return None

            digits = re.sub(r"\D", "", cleaned)

            # Israeli: +972XXXXXXXXX / 972XXXXXXXXX
            if digits.startswith("972"):
                national = digits[3:]
                # some exports include leading 0 after 972 -> strip it
                if national.startswith("0"):
                    national = national[1:]
                if 8 <= len(national) <= 10:
                    return "+972" + national
                return None

            # Israeli local: 0XXXXXXXX (landline 9) / 05XXXXXXXX (mobile 10)
            if digits.startswith("0"):
                national = digits[1:]
                if 8 <= len(national) <= 9:
                    return "+972" + national
                return None

            # Missing leading 0 (common in exports)
            # Mobile without 0: 5XXXXXXXX (9 digits)
            if len(digits) == 9 and digits.startswith("5"):
                return "+972" + digits
            # Landline without 0: 2/3/4/8/9 + 7 digits (8 digits total)
            if len(digits) == 8 and digits[0] in "23489":
                return "+972" + digits

            return None

        def _is_phone_like(value: Any) -> bool:
            if value is None:
                return False
            v = str(value).strip()
            if not v:
                return False
            return _normalize_phone_forgiving(v) is not None

        def _guess_phone_col(data_rows: list[list[str]]) -> int | None:
            if not data_rows:
                return None
            col_count = max(len(r) for r in data_rows)
            if col_count == 0:
                return None
            sample = data_rows[:200]
            best_idx = None
            best_ratio = 0.0
            for i in range(col_count):
                values = [r[i] if i < len(r) else "" for r in sample]
                non_empty = [v for v in values if str(v).strip()]
                if not non_empty:
                    continue
                phone_like = sum(1 for v in non_empty if _is_phone_like(v))
                ratio = phone_like / max(1, len(non_empty))
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_idx = i
            # Accept if at least half looks like phone OR it's the only plausible column
            if best_idx is not None and best_ratio >= 0.35:
                return best_idx
            # fallback: if only 2 columns, pick the more phone-like one even if ratio is low
            if col_count == 2:
                scores = []
                for i in range(2):
                    values = [r[i] if i < len(r) else "" for r in sample]
                    non_empty = [v for v in values if str(v).strip()]
                    phone_like = sum(1 for v in non_empty if _is_phone_like(v))
                    scores.append(phone_like)
                return 0 if scores[0] >= scores[1] else 1
            return best_idx

        def _guess_name_col(data_rows: list[list[str]], phone_idx: int | None) -> int | None:
            if not data_rows:
                return None
            col_count = max(len(r) for r in data_rows)
            if col_count == 0:
                return None
            sample = data_rows[:200]
            best_idx = None
            best_score = -1.0
            for i in range(col_count):
                if phone_idx is not None and i == phone_idx:
                    continue
                values = [str(r[i]).strip() if i < len(r) and r[i] is not None else "" for r in sample]
                non_empty = [v for v in values if v]
                if not non_empty:
                    continue
                # "name-like": mostly letters/spaces, not phone-like, short-ish
                name_like = 0
                for v in non_empty:
                    if _is_phone_like(v):
                        continue
                    if len(v) > 60:
                        continue
                    if any(ch.isalpha() for ch in v):
                        name_like += 1
                score = name_like / max(1, len(non_empty))
                if score > best_score:
                    best_score = score
                    best_idx = i
            # If only 2 cols and phone col exists, assume the other is name
            if best_idx is None and col_count == 2 and phone_idx is not None:
                return 1 - phone_idx
            return best_idx

        def _find_header_index(headers: list[str], target: str) -> int | None:
            syns = {_norm_header(s) for s in header_synonyms.get(target, [])}
            for i, h in enumerate(headers):
                if _norm_header(h) in syns:
                    return i
            return None

        def _auto_name_from_phone(normalized_phone: str) -> str:
            digits_only = re.sub(r"\D", "", normalized_phone or "")
            last4 = digits_only[-4:] if len(digits_only) >= 4 else ""
            return f"ליד {last4}" if last4 else "ליד חדש"

        def _parse_rows_from_request() -> tuple[list[list[str]], dict[str, Any]]:
            """
            Returns (table_rows, meta)
            - table_rows: list of rows (each row is list of strings), including header row if present.
            - meta: parsing metadata (filename, kind)
            """
            # JSON array support
            if request.is_json:
                payload = request.get_json(silent=True)
                if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
                    payload_rows = payload.get("rows")
                    meta = {"kind": "json", "filename": None, "list_name": payload.get("list_name")}
                else:
                    payload_rows = payload
                    meta = {"kind": "json", "filename": None, "list_name": None}

                if not isinstance(payload_rows, list):
                    raise ValueError("JSON חייב להיות מערך של שורות (array) או אובייקט עם rows")

                # If it's a list of dicts, convert to a table with headers
                if payload_rows and isinstance(payload_rows[0], dict):
                    keys: list[str] = []
                    seen = set()
                    for item in payload_rows[:1000]:
                        if not isinstance(item, dict):
                            continue
                        for k in item.keys():
                            if k not in seen:
                                seen.add(k)
                                keys.append(str(k))
                    header = keys
                    out: list[list[str]] = [header]
                    for item in payload_rows:
                        if not isinstance(item, dict):
                            continue
                        out.append([str(item.get(k, "")).strip() if item.get(k) is not None else "" for k in header])
                    return out, meta

                # If it's list-of-lists, assume it's already a table
                out_rows: list[list[str]] = []
                for item in payload_rows:
                    if isinstance(item, list):
                        out_rows.append([str(v).strip() if v is not None else "" for v in item])
                    else:
                        # scalar -> single-column
                        out_rows.append([str(item).strip()])
                return out_rows, meta

            # Multipart file upload
            if 'file' not in request.files:
                raise ValueError("לא נבחר קובץ")

            file = request.files['file']
            if not file or file.filename == '':
                raise ValueError("לא נבחר קובץ")

            filename = file.filename or ""
            lower = filename.lower()
            raw = file.read()

            if lower.endswith(".csv"):
                content = _decode_bytes(raw)
                reader = csv.reader(io.StringIO(content))
                rows = [[(c or "").strip() for c in r] for r in reader]
                return rows, {"kind": "csv", "filename": filename, "list_name": request.form.get('list_name')}

            if lower.endswith(".xlsx"):
                try:
                    import openpyxl  # type: ignore
                except Exception:
                    raise ValueError("קובץ Excel (.xlsx) נתמך רק אם openpyxl מותקן בשרת")

                wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
                ws = wb.active
                rows = []
                for r in ws.iter_rows(values_only=True):
                    rows.append([str(v).strip() if v is not None else "" for v in r])
                return rows, {"kind": "xlsx", "filename": filename, "list_name": request.form.get('list_name')}

            raise ValueError("יש להעלות קובץ CSV או Excel (.xlsx) או לשלוח JSON")

        table_rows, parse_meta = _parse_rows_from_request()
        # Remove fully empty rows
        table_rows = [r for r in table_rows if any((c or "").strip() for c in r)]
        if not table_rows:
            return jsonify({"error": "הקובץ ריק או לא מכיל שורות"}), 400

        # Decide if first row is header
        first_row = table_rows[0]
        first_has_digits = any(any(ch.isdigit() for ch in (c or "")) for c in first_row)
        has_header = False
        if not first_has_digits:
            # if it looks like header-ish text in most cells, treat as header
            headerish = sum(1 for c in first_row if _looks_like_header_cell(c))
            has_header = headerish >= max(1, int(len(first_row) * 0.5))

        headers = first_row if has_header else [f"col_{i+1}" for i in range(max(len(r) for r in table_rows))]
        data_rows = table_rows[1:] if has_header else table_rows

        # Normalize row lengths
        col_count = max(len(headers), *(len(r) for r in data_rows)) if data_rows else len(headers)
        headers = (headers + [""] * col_count)[:col_count]
        padded_rows: list[list[str]] = []
        for r in data_rows:
            rr = (r + [""] * col_count)[:col_count]
            padded_rows.append(rr)

        # Mapping: by header first, then content, then fallback
        phone_idx = _find_header_index(headers, "phone") if has_header else None
        name_idx = _find_header_index(headers, "name") if has_header else None
        city_idx = _find_header_index(headers, "city") if has_header else None
        notes_idx = _find_header_index(headers, "notes") if has_header else None

        mapping_method = "header" if phone_idx is not None else "content"
        if phone_idx is None:
            phone_idx = _guess_phone_col(padded_rows)
        if name_idx is None:
            name_idx = _guess_name_col(padded_rows, phone_idx)

        # Fallback for 2 columns: assume name+phone but still validate phone-like
        if phone_idx is None and col_count == 2:
            # pick the more phone-like one
            phone_idx = _guess_phone_col(padded_rows)
            name_idx = 1 - phone_idx if phone_idx is not None else 0
            mapping_method = "fallback"

        rows_to_import: list[dict[str, Any]] = []
        errors: list[str] = []
        errors_sample: list[str] = []

        def _add_error(msg: str) -> None:
            errors.append(msg)
            if len(errors_sample) < 20:
                errors_sample.append(msg)

        # Row numbers: +1 for header line, +1 to make 1-based
        base_row_number = 2 if has_header else 1
        for idx, row in enumerate(padded_rows):
            row_num = base_row_number + idx

            raw_phone = row[phone_idx] if phone_idx is not None and phone_idx < len(row) else ""
            normalized_phone = _normalize_phone_forgiving(raw_phone)
            if not normalized_phone:
                if str(raw_phone).strip():
                    _add_error(f"שורה {row_num}: טלפון לא תקין - {raw_phone}")
                else:
                    _add_error(f"שורה {row_num}: חסר טלפון")
                continue

            raw_name = row[name_idx].strip() if name_idx is not None and name_idx < len(row) else ""
            name = raw_name if raw_name else _auto_name_from_phone(normalized_phone)
            city = row[city_idx].strip() if city_idx is not None and city_idx < len(row) else None
            notes = row[notes_idx].strip() if notes_idx is not None and notes_idx < len(row) else None

            rows_to_import.append({
                "name": name,
                "phone": normalized_phone,
                "city": city,
                "notes": notes,
            })
        
        # Check 5000 limit
        if existing_count + len(rows_to_import) > MAX_IMPORTED_LEADS_PER_BUSINESS:
            available = MAX_IMPORTED_LEADS_PER_BUSINESS - existing_count
            return jsonify({
                "error": f"לא ניתן לייבא יותר מ-{MAX_IMPORTED_LEADS_PER_BUSINESS} לידים ברשימת השיחות היוצאות. יש לך מקום ל-{available} לידים נוספים."
            }), 400
        
        if len(rows_to_import) == 0:
            # Keep 400 only when we truly couldn't extract a single valid phone
            return jsonify({
                "error": "לא נמצאו טלפונים תקינים לייבוא",
                "errors_sample": errors_sample,
                "errors": errors_sample,  # backwards-compat for existing UI
            }), 400
        
        # Create the import list
        list_name = (parse_meta or {}).get("list_name") or f"ייבוא {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        outbound_list = OutboundLeadList()
        outbound_list.tenant_id = tenant_id
        outbound_list.name = list_name
        outbound_list.file_name = (parse_meta or {}).get("filename") or "import"
        outbound_list.total_leads = len(rows_to_import)
        db.session.add(outbound_list)
        db.session.flush()  # Get the list ID
        
        # Import leads
        imported_count = 0
        for row_data in rows_to_import:
            # Split name into first/last
            name_parts = row_data['name'].split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            lead = Lead()
            lead.tenant_id = tenant_id
            lead.first_name = first_name
            lead.last_name = last_name
            lead.phone_e164 = row_data['phone']
            lead.notes = row_data['notes']
            lead.source = "imported_outbound"
            lead.outbound_list_id = outbound_list.id
            lead.status = "new"
            db.session.add(lead)
            imported_count += 1
        
        db.session.commit()
        
        log.info(f"✅ Imported {imported_count} leads for business {tenant_id}, list_id={outbound_list.id}")
        
        return jsonify({
            "success": True,
            "list_id": outbound_list.id,
            "list_name": list_name,
            "imported_count": imported_count,
            "skipped_count": len(errors),
            "errors_sample": errors_sample,
            "errors": errors_sample,  # keep existing UI contract
            "mapping": {
                "phone": headers[phone_idx] if phone_idx is not None and phone_idx < len(headers) else None,
                "name": headers[name_idx] if name_idx is not None and name_idx < len(headers) else None,
                "method": mapping_method,
                "has_header": has_header,
                "kind": (parse_meta or {}).get("kind"),
            }
        })
        
    except Exception as e:
        log.error(f"Error importing leads: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        # Some parsing errors should be user-facing 400
        msg = str(e) or "שגיאה בייבוא הלידים"
        if any(s in msg for s in ["לא נבחר קובץ", "CSV", "Excel", "JSON", "ריק"]):
            return jsonify({"error": msg}), 400
        return jsonify({"error": f"שגיאה בייבוא הלידים: {msg}"}), 500


@outbound_bp.route("/api/outbound/import-leads", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def get_imported_leads():
    """
    BUILD 182: Get imported leads for outbound calls
    
    Query params:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 100)
    - list_id: Optional filter by list ID
    - search: Optional search query
    - statuses[]: Optional multi-status filter (e.g., ?statuses[]=new&statuses[]=contacted)
    
    Returns:
    {
        "total": 1234,
        "limit": 5000,
        "current_count": 1234,
        "page": 1,
        "page_size": 50,
        "items": [...]
    }
    """
    from flask import session
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"items": [], "total": 0, "limit": MAX_IMPORTED_LEADS_PER_BUSINESS, "message": "בחר עסק לצפייה"})
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = min(100, max(1, int(request.args.get('page_size', 50))))
        list_id = request.args.get('list_id', type=int)
        search = request.args.get('search', '').strip()
        statuses_filter = request.args.getlist('statuses[]')  # ✅ Multi-status filter
        
        # ✅ Validate status filter values against allowed statuses
        # Sanitize: only allow alphanumeric, underscore, dash (prevent injection)
        if statuses_filter:
            statuses_filter = [
                s for s in statuses_filter 
                if s and STATUS_FILTER_PATTERN.match(s) and len(s) <= 64
            ]
        
        # Build query
        query = Lead.query.filter_by(
            tenant_id=tenant_id,
            source="imported_outbound"
        )
        
        if list_id:
            query = query.filter_by(outbound_list_id=list_id)
        
        # ✅ Status filter: Support multi-status filtering with case-insensitive matching
        if statuses_filter:
            query = query.filter(func.lower(Lead.status).in_([s.lower() for s in statuses_filter]))
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    Lead.first_name.ilike(search_term),
                    Lead.last_name.ilike(search_term),
                    Lead.phone_e164.ilike(search_term)
                )
            )
        
        # Get total count
        total = query.count()
        
        # Paginate
        leads = query.order_by(Lead.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        items = []
        for lead in leads:
            items.append({
                "id": lead.id,
                "name": lead.full_name,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "phone": lead.phone_e164,
                "status": lead.status,
                "notes": lead.notes,
                "list_id": lead.outbound_list_id,
                "created_at": lead.created_at.isoformat() if lead.created_at else None
            })
        
        return jsonify({
            "total": total,
            "limit": MAX_IMPORTED_LEADS_PER_BUSINESS,
            "current_count": total,
            "page": page,
            "page_size": page_size,
            "items": items
        })
        
    except Exception as e:
        log.error(f"Error fetching imported leads: {e}")
        return jsonify({"error": "שגיאה בטעינת הלידים"}), 500


@outbound_bp.route("/api/outbound/import-leads/<int:lead_id>", methods=["DELETE"])
@require_api_auth(['system_admin', 'owner', 'admin'])
def delete_imported_lead(lead_id: int):
    """
    BUILD 182: Delete a single imported lead
    
    Only allows deletion of leads with source="imported_outbound"
    Regular CRM leads cannot be deleted from this endpoint.
    """
    from flask import session
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני מחיקת ליד"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=tenant_id
        ).first()
        
        if not lead:
            return jsonify({"error": "ליד לא נמצא"}), 404
        
        # Only allow deletion of imported leads
        if lead.source != "imported_outbound":
            return jsonify({"error": "ניתן למחוק רק לידים מיובאים מרשימת שיחות יוצאות"}), 403
        
        db.session.delete(lead)
        db.session.commit()
        
        log.info(f"🗑️ Deleted imported lead {lead_id} for business {tenant_id}")
        
        return jsonify({"success": True, "message": "הליד נמחק בהצלחה"})
        
    except Exception as e:
        log.error(f"Error deleting imported lead: {e}")
        db.session.rollback()
        return jsonify({"error": "שגיאה במחיקת הליד"}), 500


@outbound_bp.route("/api/outbound/import-leads/bulk-delete", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin'])
def bulk_delete_imported_leads():
    """
    BUILD 182: Bulk delete imported leads
    
    Request body:
    {
        "lead_ids": [1, 2, 3] OR
        "delete_all": true (delete all imported leads)
    }
    """
    from flask import session
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני מחיקה"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "נתונים חסרים"}), 400
    
    try:
        if data.get('delete_all'):
            # Delete all imported leads for this business
            deleted = Lead.query.filter_by(
                tenant_id=tenant_id,
                source="imported_outbound"
            ).delete()
            db.session.commit()
            
            log.info(f"🗑️ Bulk deleted {deleted} imported leads for business {tenant_id}")
            
            return jsonify({
                "success": True,
                "deleted_count": deleted,
                "message": f"נמחקו {deleted} לידים"
            })
        
        lead_ids = data.get('lead_ids', [])
        if not lead_ids:
            return jsonify({"error": "לא נבחרו לידים למחיקה"}), 400
        
        # Only delete imported leads
        deleted = Lead.query.filter(
            Lead.id.in_(lead_ids),
            Lead.tenant_id == tenant_id,
            Lead.source == "imported_outbound"
        ).delete(synchronize_session=False)
        
        db.session.commit()
        
        log.info(f"🗑️ Bulk deleted {deleted} imported leads for business {tenant_id}")
        
        return jsonify({
            "success": True,
            "deleted_count": deleted,
            "message": f"נמחקו {deleted} לידים"
        })
        
    except Exception as e:
        log.error(f"Error bulk deleting imported leads: {e}")
        db.session.rollback()
        return jsonify({"error": "שגיאה במחיקת הלידים"}), 500


@outbound_bp.route("/api/outbound/import-lists", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def get_import_lists():
    """
    BUILD 182: Get all import lists for the business
    """
    from flask import session
    from server.models_sql import OutboundLeadList
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"lists": []})
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        lists = OutboundLeadList.query.filter_by(
            tenant_id=tenant_id
        ).order_by(OutboundLeadList.created_at.desc()).all()
        
        result = []
        for lst in lists:
            # Count current leads in list
            lead_count = Lead.query.filter_by(
                tenant_id=tenant_id,
                outbound_list_id=lst.id
            ).count()
            
            result.append({
                "id": lst.id,
                "name": lst.name,
                "file_name": lst.file_name,
                "total_leads": lst.total_leads,
                "current_leads": lead_count,
                "created_at": lst.created_at.isoformat() if lst.created_at else None
            })
        
        return jsonify({"lists": result})
        
    except Exception as e:
        log.error(f"Error fetching import lists: {e}")
        return jsonify({"error": "שגיאה בטעינת רשימות הייבוא"}), 500


@outbound_bp.route("/api/outbound/bulk-enqueue", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def bulk_enqueue_outbound_calls():
    """
    Bulk enqueue outbound calls with concurrency control
    
    Request body:
    {
        "lead_ids": [1, 2, 3, ...],
        "concurrency": 3,
        "outbound_list_id": 12 (optional)
    }
    
    Returns:
    {
        "run_id": "123",
        "queued": 500
    }
    """
    from flask import session
    from server.models_sql import OutboundCallRun, OutboundCallJob
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני הפעלת שיחות"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "נתונים חסרים"}), 400
    
    lead_ids = data.get("lead_ids", [])
    concurrency = data.get("concurrency", 3)
    outbound_list_id = data.get("outbound_list_id")
    
    if not lead_ids or not isinstance(lead_ids, list):
        return jsonify({"error": "יש לבחור לפחות ליד אחד"}), 400
    
    # Validate concurrency
    if concurrency < 1 or concurrency > 10:
        return jsonify({"error": "מספר שיחות במקביל חייב להיות בין 1 ל-10"}), 400
    
    try:
        # Verify all leads belong to this tenant
        leads = Lead.query.filter(
            Lead.id.in_(lead_ids),
            Lead.tenant_id == tenant_id
        ).all()
        
        if len(leads) != len(lead_ids):
            return jsonify({"error": "לא נמצאו כל הלידים שנבחרו"}), 404
        
        # Create run
        run = OutboundCallRun()
        run.business_id = tenant_id
        run.outbound_list_id = outbound_list_id
        run.concurrency = concurrency
        run.total_leads = len(lead_ids)
        run.queued_count = len(lead_ids)
        run.status = "running"
        db.session.add(run)
        db.session.flush()
        
        # Create jobs for each lead
        for lead_id in lead_ids:
            job = OutboundCallJob()
            job.run_id = run.id
            job.lead_id = lead_id
            job.status = "queued"
            db.session.add(job)
        
        db.session.commit()
        
        log.info(f"✅ Created bulk call run {run.id} with {len(lead_ids)} leads, concurrency={concurrency}")
        
        # Start background worker to process the queue
        from threading import Thread
        thread = Thread(target=process_bulk_call_run, args=(run.id,), daemon=True)
        thread.start()
        
        return jsonify({
            "run_id": run.id,
            "queued": len(lead_ids)
        }), 201
        
    except Exception as e:
        log.error(f"Error creating bulk call run: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": f"שגיאה ביצירת הרצה: {str(e)}"}), 500


@outbound_bp.route("/api/outbound/runs/<int:run_id>", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def get_run_status(run_id: int):
    """
    Get status of bulk call run
    
    Returns:
    {
        "run_id": 123,
        "status": "running",
        "queued": 450,
        "in_progress": 3,
        "completed": 47,
        "failed": 0,
        "last_error": null
    }
    """
    from flask import session
    from server.models_sql import OutboundCallRun
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            # System admin can view any run, get tenant from run
            run = OutboundCallRun.query.get(run_id)
            if not run:
                return jsonify({"error": "הרצה לא נמצאה"}), 404
        else:
            return jsonify({"error": "אין גישה לעסק"}), 403
    else:
        # Regular user: verify run belongs to their tenant
        run = OutboundCallRun.query.filter_by(
            id=run_id,
            business_id=tenant_id
        ).first()
        
        if not run:
            return jsonify({"error": "הרצה לא נמצאה"}), 404
    
    return jsonify({
        "run_id": run.id,
        "status": run.status,
        "queued": run.queued_count,
        "in_progress": run.in_progress_count,
        "completed": run.completed_count,
        "failed": run.failed_count,
        "last_error": run.last_error,
        "total_leads": run.total_leads,
        "concurrency": run.concurrency,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None
    })


@outbound_bp.route("/api/outbound/stop-queue", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def stop_queue():
    """
    Stop an active bulk call queue/run
    
    Request body:
    {
        "run_id": 123
    }
    """
    from flask import session
    from server.models_sql import OutboundCallRun
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            # System admin can stop any run
            pass
        else:
            return jsonify({"error": "אין גישה לעסק"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "נתונים חסרים"}), 400
    
    run_id = data.get('run_id')
    if not run_id:
        return jsonify({"error": "חסר run_id"}), 400
    
    try:
        # Get run (verify it belongs to tenant if not system admin)
        if tenant_id:
            run = OutboundCallRun.query.filter_by(
                id=run_id,
                business_id=tenant_id
            ).first()
        else:
            run = OutboundCallRun.query.get(run_id)
        
        if not run:
            return jsonify({"error": "הרצה לא נמצאה"}), 404
        
        # Mark as cancelled
        run.status = "cancelled"
        db.session.commit()
        
        log.info(f"✅ Stopped queue run {run_id}")
        
        return jsonify({
            "success": True,
            "message": "התור הופסק בהצלחה"
        })
        
    except Exception as e:
        log.error(f"Error stopping queue {run_id}: {e}")
        db.session.rollback()
        return jsonify({"error": "שגיאה בעצירת התור"}), 500


def fill_queue_slots_for_job(job_id: int):
    """
    Called when a call completes - tries to fill available slots in the queue
    This is the event-driven approach instead of polling
    """
    from server.app_factory import get_process_app
    from server.models_sql import OutboundCallRun, OutboundCallJob, Lead, Business, CallLog
    from datetime import datetime
    
    app = get_process_app()
    
    with app.app_context():
        try:
            # Get the job and run
            job = OutboundCallJob.query.get(job_id)
            if not job:
                log.warning(f"[FillSlots] Job {job_id} not found")
                return
            
            run = OutboundCallRun.query.get(job.run_id)
            if not run or run.status != "running":
                log.info(f"[FillSlots] Run {job.run_id} not running, skipping")
                return
            
            log.info(f"[FillSlots] Filling slots for run {run.id} after job {job_id} completed")
            
            # Get business details
            business = Business.query.get(run.business_id)
            if not business or not business.phone_e164:
                log.error(f"[FillSlots] Business {run.business_id} has no phone")
                return
            
            from_phone = business.phone_e164
            business_name = business.name or "העסק"
            host = get_public_host()
            
            # Check how many active calls we have
            active_count = OutboundCallJob.query.filter_by(
                run_id=run.id,
                status="calling"
            ).count()
            
            # Fill available slots
            while active_count < run.concurrency:
                # Get next queued job
                next_job = OutboundCallJob.query.filter_by(
                    run_id=run.id,
                    status="queued"
                ).order_by(OutboundCallJob.id).first()
                
                if not next_job:
                    # No more jobs queued
                    if active_count == 0:
                        # All done!
                        run.status = "completed"
                        run.completed_at = datetime.utcnow()
                        db.session.commit()
                        log.info(f"[FillSlots] Run {run.id} completed - all calls finished")
                    break
                
                # Start this call
                try:
                    lead = Lead.query.get(next_job.lead_id)
                    if not lead or not lead.phone_e164:
                        next_job.status = "failed"
                        next_job.error_message = "אין מספר טלפון לליד"
                        next_job.completed_at = datetime.utcnow()
                        run.failed_count += 1
                        run.queued_count -= 1
                        db.session.commit()
                        continue
                    
                    # Update job status
                    next_job.status = "calling"
                    next_job.started_at = datetime.utcnow()
                    run.in_progress_count += 1
                    run.queued_count -= 1
                    db.session.commit()
                    
                    # Normalize phone
                    normalized_phone = normalize_israeli_phone(lead.phone_e164)
                    
                    # Create call log
                    call_log = CallLog()
                    call_log.business_id = run.business_id
                    call_log.lead_id = lead.id
                    call_log.from_number = from_phone
                    call_log.to_number = normalized_phone
                    call_log.direction = "outbound"
                    call_log.status = "initiated"
                    call_log.call_status = "initiated"
                    db.session.add(call_log)
                    db.session.flush()
                    
                    next_job.call_log_id = call_log.id
                    db.session.commit()
                    
                    # Initiate Twilio call
                    lead_name = lead.full_name or "לקוח"
                    webhook_url = f"https://{host}/webhook/outbound_call"
                    webhook_url += f"?call_id={call_log.id}"
                    webhook_url += f"&lead_id={lead.id}"
                    webhook_url += f"&lead_name={quote(lead_name, safe='')}"
                    webhook_url += f"&business_id={run.business_id}"
                    webhook_url += f"&business_name={quote(business_name, safe='')}"
                    webhook_url += f"&run_id={run.id}"
                    webhook_url += f"&job_id={next_job.id}"
                    
                    client = get_twilio_client()
                    
                    amd_callback_url = f"https://{host}/webhook/amd_status"
                    
                    try:
                        twilio_call = client.calls.create(
                            to=normalized_phone,
                            from_=from_phone,
                            url=webhook_url,
                            status_callback=f"https://{host}/webhook/call_status",
                            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                            machine_detection="DetectMessageEnd",
                            async_amd=True,
                            async_amd_status_callback=amd_callback_url,
                            async_amd_status_callback_method="POST",
                            record=True
                        )
                    except TypeError:
                        twilio_call = client.calls.create(
                            to=normalized_phone,
                            from_=from_phone,
                            url=webhook_url,
                            status_callback=f"https://{host}/webhook/call_status",
                            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                            record=True
                        )
                    
                    call_log.call_sid = twilio_call.sid
                    next_job.call_sid = twilio_call.sid
                    db.session.commit()
                    
                    log.info(f"[FillSlots] Started call for lead {lead.id}, job {next_job.id}, call_sid={twilio_call.sid}")
                    active_count += 1
                    
                except Exception as e:
                    log.error(f"[FillSlots] Error starting call for job {next_job.id}: {e}")
                    next_job.status = "failed"
                    next_job.error_message = str(e)
                    next_job.completed_at = datetime.utcnow()
                    run.in_progress_count -= 1
                    run.failed_count += 1
                    db.session.commit()
                    
        except Exception as e:
            log.error(f"[FillSlots] Error in fill_queue_slots_for_job: {e}")
            import traceback
            traceback.print_exc()


def process_bulk_call_run(run_id: int):
    """
    Background worker to process bulk call run
    Respects concurrency limits and processes queue
    """
    from server.app_factory import get_process_app
    from server.models_sql import OutboundCallRun, OutboundCallJob, Lead, Business, CallLog
    import time
    
    app = get_process_app()
    
    with app.app_context():
        try:
            run = OutboundCallRun.query.get(run_id)
            if not run:
                log.error(f"Run {run_id} not found")
                return
            
            log.info(f"[BulkCall] Starting run {run_id} with concurrency={run.concurrency}")
            
            # Get business details
            business = Business.query.get(run.business_id)
            if not business or not business.phone_e164:
                run.status = "failed"
                run.last_error = "מספר טלפון של העסק לא מוגדר"
                db.session.commit()
                return
            
            from_phone = business.phone_e164
            business_name = business.name or "העסק"
            host = get_public_host()
            
            # Process jobs in queue
            while True:
                # Check if queue was stopped
                db.session.refresh(run)
                if run.status == "cancelled":
                    log.info(f"[BulkCall] Run {run_id} was cancelled, stopping")
                    break
                
                # Get current active count
                active_jobs = OutboundCallJob.query.filter_by(
                    run_id=run_id,
                    status="calling"
                ).count()
                
                # Check if we can start more calls
                if active_jobs < run.concurrency:
                    # Get next queued job
                    next_job = OutboundCallJob.query.filter_by(
                        run_id=run_id,
                        status="queued"
                    ).order_by(OutboundCallJob.id).first()
                    
                    if next_job:
                        # Start this call
                        try:
                            lead = Lead.query.get(next_job.lead_id)
                            if not lead or not lead.phone_e164:
                                next_job.status = "failed"
                                next_job.error_message = "אין מספר טלפון לליד"
                                next_job.completed_at = datetime.utcnow()
                                run.failed_count += 1
                                run.queued_count -= 1
                                db.session.commit()
                                continue
                            
                            # Update job status
                            next_job.status = "calling"
                            next_job.started_at = datetime.utcnow()
                            run.in_progress_count += 1
                            run.queued_count -= 1
                            db.session.commit()
                            
                            # Normalize phone
                            normalized_phone = normalize_israeli_phone(lead.phone_e164)
                            
                            # Create call log
                            call_log = CallLog()
                            call_log.business_id = run.business_id
                            call_log.lead_id = lead.id
                            call_log.from_number = from_phone
                            call_log.to_number = normalized_phone
                            call_log.direction = "outbound"
                            call_log.status = "initiated"
                            call_log.call_status = "initiated"
                            db.session.add(call_log)
                            db.session.flush()
                            
                            next_job.call_log_id = call_log.id
                            db.session.commit()
                            
                            # Initiate Twilio call
                            lead_name = lead.full_name or "לקוח"
                            webhook_url = f"https://{host}/webhook/outbound_call"
                            webhook_url += f"?call_id={call_log.id}"
                            webhook_url += f"&lead_id={lead.id}"
                            webhook_url += f"&lead_name={quote(lead_name, safe='')}"
                            webhook_url += f"&business_id={run.business_id}"
                            webhook_url += f"&business_name={quote(business_name, safe='')}"
                            webhook_url += f"&run_id={run_id}"
                            webhook_url += f"&job_id={next_job.id}"
                            
                            client = get_twilio_client()
                            
                            # ✅ AMD: Correct parameters for Twilio Python SDK
                            amd_callback_url = f"https://{host}/webhook/amd_status"
                            
                            try:
                                # Try with correct AMD parameters (async_amd + async_amd_status_callback)
                                twilio_call = client.calls.create(
                                    to=normalized_phone,
                                    from_=from_phone,
                                    url=webhook_url,
                                    status_callback=f"https://{host}/webhook/call_status",
                                    status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                                    # ✅ AMD: Correct Twilio Python SDK parameters
                                    machine_detection="DetectMessageEnd",
                                    async_amd=True,
                                    async_amd_status_callback=amd_callback_url,
                                    async_amd_status_callback_method="POST",
                                    record=True
                                )
                            except TypeError as amd_error:
                                # Fallback: AMD parameters not supported by SDK version - create call without AMD
                                log.warning(f"[BulkCall] AMD parameters not supported (SDK version issue): {amd_error}. Creating call without AMD.")
                                twilio_call = client.calls.create(
                                    to=normalized_phone,
                                    from_=from_phone,
                                    url=webhook_url,
                                    status_callback=f"https://{host}/webhook/call_status",
                                    status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                                    record=True
                                )
                            
                            call_log.call_sid = twilio_call.sid
                            next_job.call_sid = twilio_call.sid
                            db.session.commit()
                            
                            log.info(f"[BulkCall] Started call for lead {lead.id}, job {next_job.id}, call_sid={twilio_call.sid}")
                            
                        except Exception as e:
                            log.error(f"[BulkCall] Error starting call for job {next_job.id}: {e}")
                            next_job.status = "failed"
                            next_job.error_message = str(e)
                            next_job.completed_at = datetime.utcnow()
                            run.in_progress_count -= 1
                            run.failed_count += 1
                            run.last_error = str(e)[:500]
                            db.session.commit()
                    else:
                        # No more queued jobs
                        if active_jobs == 0:
                            # All done
                            run.status = "completed"
                            run.completed_at = datetime.utcnow()
                            db.session.commit()
                            log.info(f"[BulkCall] Run {run_id} completed")
                            break
                        else:
                            # Wait for active calls to complete
                            time.sleep(2)
                else:
                    # At capacity, wait
                    time.sleep(2)
                
                # Refresh run to get latest counts
                db.session.refresh(run)
            
        except Exception as e:
            log.error(f"[BulkCall] Error in run {run_id}: {e}")
            import traceback
            traceback.print_exc()
            
            # Mark run as failed
            try:
                run = OutboundCallRun.query.get(run_id)
                if run:
                    run.status = "failed"
                    run.last_error = str(e)[:500]
                    db.session.commit()
            except:
                pass
