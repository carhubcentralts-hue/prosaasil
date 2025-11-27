"""
Auto Meeting Scheduler - יצירת פגישות אוטומטית מתוך שיחות AI
"""
from datetime import datetime, timedelta
from server.models_sql import Appointment, Customer, Business, CallLog
from server.db import db
from sqlalchemy import and_
import re
import time
import pytz

# 🔥 Israel timezone for converting naive datetimes
tz = pytz.timezone("Asia/Jerusalem")

def create_auto_appointment_from_call(call_sid: str, lead_info: dict, conversation_history: list, phone_number: str = ""):
    """
    יצירת פגישה אוטומטית מתוך שיחה כאשר יש מספיק מידע על הליד
    
    Args:
        call_sid: מזהה השיחה
        lead_info: המידע שנאסף על הליד (מפונקציית _analyze_lead_completeness) 
        conversation_history: היסטוריית השיחה
        phone_number: מספר טלפון של הלקוח
        
    Returns:
        dict: תוצאת יצירת הפגישה
    """
    try:
        if not lead_info.get('meeting_ready', False):
            return {'success': False, 'reason': 'לא מספיק מידע לקביעת פגישה'}
        
        # נסיון למצוא call_log קיים
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        if not call_log:
            print(f"⚠️ Call log not found for {call_sid} - creating appointment without call connection")
        
        # איתור או יצירת לקוח
        customer = None
        customer_name = None
        
        # חיפוש שם בהיסטוריית השיחה
        full_conversation = ' '.join([turn.get('user', '') + ' ' + turn.get('bot', '') for turn in conversation_history if isinstance(turn, dict)])
        
        # זיהוי שם (דפוסים עבריים נפוצים)
        name_patterns = [
            r'אני ([א-ת]+)',
            r'קוראים לי ([א-ת]+)',
            r'השם שלי ([א-ת]+)', 
            r'השם ([א-ת]+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, full_conversation)
            if match:
                customer_name = match.group(1).strip()
                break
        
        # חיפוש לקוח קיים או יצירת חדש
        # ✅ BUILD 155 FINAL: קבלת business_id מה-call_log - אין fallback!
        business_id = call_log.business_id if call_log else None
        if not business_id:
            # ✅ BUILD 155 SECURITY: NO fallback - must have deterministic business_id
            print(f"❌ Cannot resolve business_id for call {call_sid} - no fallback allowed (multi-tenant security)")
            return {'success': False, 'reason': 'לא ניתן לזהות את העסק - נדרש business_id'}
        
        if phone_number:
            # ✅ FIX: Query by phone_e164 not phone (correct column name)
            customer = Customer.query.filter_by(phone_e164=phone_number, business_id=business_id).first()
            if not customer:
                # יצירת לקוח חדש
                customer = Customer()
                customer.name = customer_name or f"לקוח מטלפון {phone_number[-4:]}"
                customer.phone_e164 = phone_number
                customer.status = "lead"
                customer.business_id = business_id  # ✅ FIX: Use correct business_id from call
                
                db.session.add(customer)
                db.session.flush()  # כדי לקבל ID
                
        # ✅ UNIFIED: Use shared parser (no duplication!)
        from server.services.appointment_parser import parse_appointment_info
        
        # איסוף מידע מהשיחה
        collected = lead_info.get('collected', {})
        
        # Parse all info at once
        parsed_info = parse_appointment_info(full_conversation)
        
        # ✅ FIX: Merge with collected data (don't lose existing info!)
        area = parsed_info.get('area') or collected.get('area', '')
        property_type = parsed_info.get('property_type') or collected.get('property_type', '')
        budget_info = parsed_info.get('budget') or collected.get('budget', '')
        
        # יצירת כותרת מפורטת לפגישה
        title_parts = []
        if customer_name:
            title_parts.append(customer_name)
        if property_type:
            title_parts.append(property_type)
        if area:
            title_parts.append(f"ב{area}")
        
        appointment_title = " - ".join(title_parts) if title_parts else "פגישה ליעוץ נדל\"ן"
        
        # יצירת תיאור מפורט
        description_parts = []
        if collected.get('area'):
            description_parts.append(f"אזור מועדף: {area}")
        if collected.get('property_type'):
            description_parts.append(f"סוג נכס: {property_type}")
        if collected.get('budget'):
            description_parts.append(f"תקציב: {budget_info}")
        if collected.get('timing'):
            description_parts.append("התזמון: דחיפות נמוכה-בינונית")
        
        description = "פגישה שנוצרה אוטומטית מתוך שיחת טלפון.\n\n" + "\n".join(description_parts)
        
        # ✅ BUILD 104: ניתוח זמן אמיתי מהשיחה!
        from server.services.time_parser import get_meeting_time_from_conversation
        
        # ✅ DEBUG: הדפס את השיחה שאנחנו מנתחים
        print(f"🔍 AUTO_MEETING: Analyzing {len(conversation_history)} conversation turns for meeting time")
        for i, turn in enumerate(conversation_history[-3:]):  # 3 תורות אחרונים
            print(f"  Turn {i}: user='{turn.get('user', '')[:50]}...', bot='{turn.get('bot', '')[:50]}...'")
        
        # 🚨 CRITICAL: בדוק תחילה אם יש סירוב בתור האחרון!
        if conversation_history:
            last_user_msg = conversation_history[-1].get('user', '').lower()
            rejection_keywords = ['לא תודה', 'לא רוצה', 'לא מעוניין', 'ביי', 'להתראות', 'תודה לא']
            
            if any(keyword in last_user_msg for keyword in rejection_keywords):
                print(f"🚫 AUTO_MEETING: User REJECTED in last turn - NOT creating appointment!")
                return {'success': False, 'reason': 'המשתמש סירב לקביעת פגישה'}
        
        # נסה לנתח זמן מהשיחה
        parsed_time = get_meeting_time_from_conversation(conversation_history)
        
        if parsed_time:
            # ✅ נמצא זמן מוסכם בשיחה!
            meeting_time, end_time = parsed_time
            print(f"✅ AUTO_MEETING: Parsed meeting time from conversation: {meeting_time.strftime('%Y-%m-%d %H:%M')}")
        else:
            # ⚠️ Fallback: זמן default (אם לא נמצא זמן בשיחה)
            now = datetime.now()
            
            # מחפשים יום עסקים הבא (לא שבת)
            days_ahead = 1
            while True:
                potential_date = now + timedelta(days=days_ahead)
                # בדוק שזה לא שבת (weekday() == 5)
                if potential_date.weekday() != 5:
                    break
                days_ahead += 1
            
            # קביעת זמן - 10:00 בבוקר או 16:00 אחר הצהריים
            meeting_time = potential_date.replace(hour=10, minute=0, second=0, microsecond=0)
            if now.hour > 14:  # אם כבר אחרי 14:00, קבע ל-16:00
                meeting_time = meeting_time.replace(hour=16)
            
            end_time = meeting_time + timedelta(hours=1)  # פגישה של שעה
            print(f"⚠️ Using default meeting time: {meeting_time}")
        
        # 🔥 CRITICAL: Check for overlapping appointments before creating
        existing = Appointment.query.filter(
            Appointment.business_id == business_id,
            Appointment.start_time < end_time,
            Appointment.end_time > meeting_time,
            Appointment.status.in_(['scheduled', 'confirmed'])
        ).first()
        
        if existing:
            # Try to find next available slot (1 hour later)
            meeting_time = meeting_time + timedelta(hours=1)
            end_time = meeting_time + timedelta(hours=1)
            
            # Check again
            existing = Appointment.query.filter(
                Appointment.business_id == business_id,
                Appointment.start_time < end_time,
                Appointment.end_time > meeting_time,
                Appointment.status.in_(['scheduled', 'confirmed'])
            ).first()
            
            if existing:
                # If still conflicted, return error
                return {
                    'success': False,
                    'reason': f'חפיפה עם פגישה קיימת בשעה {existing.start_time.strftime("%H:%M")}',
                    'conflict': True
                }
        
        # יצירת הפגישה
        appointment = Appointment()
        # ✅ FIX: Use business_id from call, not default
        appointment.business_id = business_id
        appointment.customer_id = customer.id if customer else None
        appointment.call_log_id = call_log.id if call_log else None
        appointment.title = appointment_title
        appointment.description = description
        appointment.start_time = meeting_time
        appointment.end_time = end_time
        appointment.status = 'scheduled'  # נקבעה אבל צריך אישור
        appointment.appointment_type = 'viewing'
        appointment.priority = 'high'  # פגישה מטלפון בעדיפות גבוהה
        appointment.contact_name = customer_name or f"לקוח {phone_number[-4:] if phone_number else 'לא ידוע'}"
        appointment.contact_phone = phone_number
        appointment.notes = f"נוצרה אוטומטית מתוך שיחה {call_sid}\nרמת השלמת מידע: {lead_info.get('completed_count', 0)}/5"
        appointment.auto_generated = True
        appointment.source = 'phone_call'
        appointment.created_by = None  # נוצר על ידי המערכת
        
        # ✅ BUILD 144: Generate and save call summary for the appointment
        try:
            from server.services.summary_service import summarize_conversation
            
            # Build transcription from conversation history
            transcription_parts = []
            for turn in conversation_history:
                if isinstance(turn, dict):
                    if turn.get('user'):
                        transcription_parts.append(f"לקוח: {turn['user']}")
                    if turn.get('bot'):
                        transcription_parts.append(f"נציג: {turn['bot']}")
            
            transcription = "\n".join(transcription_parts)
            
            if transcription:
                # Get business info for context
                business = Business.query.get(business_id)
                business_name = business.name if business else None
                
                # Generate dynamic AI summary
                call_summary = summarize_conversation(
                    transcription=transcription,
                    call_sid=call_sid,
                    business_name=business_name
                )
                appointment.call_summary = call_summary
                print(f"✅ AUTO_MEETING: Call summary generated for appointment")
        except Exception as e:
            print(f"⚠️ AUTO_MEETING: Failed to generate call summary: {e}")
            # Continue without summary - not critical
        
        db.session.add(appointment)
        db.session.commit()
        
        # 🔥 Add timezone before returning for API responses
        meeting_time_aware = tz.localize(meeting_time)
        
        return {
            'success': True,
            'appointment_id': appointment.id,
            'meeting_time': meeting_time_aware.isoformat(),  # With timezone
            'customer_name': customer_name,
            'title': appointment_title,
            'message': f'נוצרה פגישה ל{meeting_time.strftime("%d/%m/%Y בשעה %H:%M")}'
        }
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error creating auto appointment: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': 'שגיאה ביצירת פגישה אוטומטית'
        }

def check_and_create_appointment(call_sid: str, lead_info: dict, conversation_history: list, phone_number: str = ""):
    """
    בדיקה ויצירת פגישה אם נדרש - נקרא מתוך עיבוד השיחה
    ✅ BUILD 100.16: Threshold lowered to 3/5 fields for easier appointment creation
    """
    # בדוק שלא נוצרה כבר פגישה לשיחה הזו
    call_log = CallLog.query.filter_by(call_sid=call_sid).first()
    if call_log:
        existing_appointment = Appointment.query.filter_by(call_log_id=call_log.id).first()
    else:
        existing_appointment = None
    
    if existing_appointment:
        return {'success': False, 'reason': 'כבר קיימת פגישה לשיחה זו'}
    
    # ✅ BUILD 100.16: Lowered threshold from >=4 to >=3 (area + property_type + phone)
    if lead_info.get('meeting_ready', False) and lead_info.get('completed_count', 0) >= 3:
        result = create_auto_appointment_from_call(call_sid, lead_info, conversation_history, phone_number)
        if result['success']:
            print(f"✅ Auto appointment created: {result['appointment_id']} for call {call_sid}")
        return result
    
    return {'success': False, 'reason': 'לא מספיק מידע לקביעת פגישה'}