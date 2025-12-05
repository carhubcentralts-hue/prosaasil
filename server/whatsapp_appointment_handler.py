"""
WhatsApp Appointment Handler - ניהול פגישות דרך וואטסאפ
"""
from datetime import datetime, timedelta
from server.models_sql import Appointment, Customer, Business, WhatsAppMessage, db
from server.whatsapp_templates import send_template_message, select_template
import re
import json
from typing import Dict, List, Optional
import requests
import os
import pytz

# 🔥 Israel timezone for converting naive datetimes
tz = pytz.timezone("Asia/Jerusalem")

def extract_appointment_info_from_whatsapp(message_text: str, customer_phone: str) -> Dict:
    """
    🔥 BUILD 200: מחלץ מידע לפגישה מהודעת ווצאפ - GENERIC for any business type
    """
    info = {
        'has_request': False,
        'area': '',
        'service_type': '',  # 🔥 BUILD 200: Generic service_type, not property_type
        'urgency': 'medium',
        'preferred_time': '',
        'meeting_ready': False
    }
    
    text = message_text.lower()
    
    # זיהוי בקשה לפגישה - generic keywords
    meeting_keywords = [
        'פגישה', 'לראות', 'לבקר', 'להיפגש',
        'מתי אפשר', 'מתי נוכל', 'אפשר לקבוע', 'בואו נפגש',
        'תור', 'קביעת', 'לקבוע'
    ]
    
    if any(keyword in text for keyword in meeting_keywords):
        info['has_request'] = True
    
    # 🔥 BUILD 200: Use dynamic parser - only area extraction
    from server.services.appointment_parser import parse_appointment_info_dynamic
    
    # Parse area only - other fields come from AI prompt
    parsed_info = parse_appointment_info_dynamic(text)
    if parsed_info.get('area'):
        info['area'] = parsed_info['area']
    
    # זיהוי דחיפות
    if any(word in text for word in ['דחוף', 'מיידי', 'היום', 'מחר']):
        info['urgency'] = 'high'
    elif any(word in text for word in ['לא ממהר', 'בזמן הקרוב', 'בשבועים הקרובים']):
        info['urgency'] = 'low'
    
    # זיהוי זמן מועדף
    time_patterns = [
        r'בשעה (\d{1,2}):?(\d{0,2})',
        r'ב-?(\d{1,2})',
        r'(בוקר|צהריים|אחר הצהריים|ערב)'
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text)
        if match:
            info['preferred_time'] = match.group(0)
            break
    
    # 🔥 BUILD 200: Simplified criteria - generic for any business
    criteria_met = sum([
        bool(info['has_request']),
        bool(info['area']),
        True  # מספר טלפון תמיד קיים
    ])
    
    info['meeting_ready'] = criteria_met >= 2  # Has request + phone = ready
    info['criteria_score'] = criteria_met
    
    return info

def create_whatsapp_appointment(customer_phone: str, message_text: str, whatsapp_message_id: Optional[int] = None, business_id: Optional[int] = None) -> Dict:
    """
    יוצר פגישה מתוך הודעת ווצאפ
    
    Args:
        customer_phone: מספר טלפון של הלקוח
        message_text: תוכן ההודעה
        whatsapp_message_id: מזהה ההודעה ב-DB
        business_id: מזהה העסק (אם ידוע)
    """
    try:
        # חילוץ מידע מההודעה
        appointment_info = extract_appointment_info_from_whatsapp(message_text, customer_phone)
        
        if not appointment_info['meeting_ready']:
            return {
                'success': False,
                'reason': 'לא מספיק מידע לקביעת פגישה',
                'score': appointment_info['criteria_score']
            }
        
        # ✅ BUILD 155 SECURITY: Require explicit business_id - NO fallback to first business!
        # This prevents cross-tenant data leakage in multi-tenant environments
        if not business_id:
            return {
                'success': False,
                'reason': 'business_id נדרש ליצירת פגישה',
                'error': 'MISSING_BUSINESS_ID'
            }
        
        # חיפוש או יצירת לקוח
        # ✅ FIX: Filter by both phone AND business_id for multi-tenant safety
        customer = Customer.query.filter_by(phone_e164=customer_phone, business_id=business_id).first()
        if not customer:
            # יצירת לקוח חדש
            customer = Customer()
            customer.name = f"לקוח מווצאפ {customer_phone[-4:]}"
            customer.phone_e164 = customer_phone
            customer.status = "lead"
            customer.business_id = business_id  # ✅ FIX: Use correct business_id
            
            db.session.add(customer)
            db.session.flush()
        
        # 🔥 BUILD 200: בניית כותרת ותיאור - GENERIC for any business type
        title_parts = [customer.name or f"לקוח {customer_phone[-4:]}"]
        if appointment_info.get('service_type'):
            title_parts.append(appointment_info['service_type'])
        if appointment_info['area']:
            title_parts.append(f"ב{appointment_info['area']}")
        
        title = " - ".join(title_parts)
        
        description_parts = [
            "פגישה שנוצרה אוטומטית מהודעת ווצאפ:",
            f"הודעה מקורית: {message_text[:100]}..."
        ]
        
        if appointment_info['area']:
            description_parts.append(f"אזור: {appointment_info['area']}")
        if appointment_info.get('service_type'):
            description_parts.append(f"שירות: {appointment_info['service_type']}")
        if appointment_info['preferred_time']:
            description_parts.append(f"זמן מועדף: {appointment_info['preferred_time']}")
        
        description = "\n".join(description_parts)
        
        # חישוב זמן פגישה
        now = datetime.now()
        
        # אם דחוף - מחר, אחרת יומיים
        days_ahead = 1 if appointment_info['urgency'] == 'high' else 2
        
        # מחפש יום עסקים (לא שבת)
        while True:
            potential_date = now + timedelta(days=days_ahead)
            if potential_date.weekday() != 5:  # לא שבת
                break
            days_ahead += 1
        
        # זמן ברירת מחדל לפי דחיפות
        if appointment_info['urgency'] == 'high':
            meeting_hour = 10  # 10:00 בבוקר
        else:
            meeting_hour = 14  # 14:00 אחה"צ
        
        meeting_time = potential_date.replace(hour=meeting_hour, minute=0, second=0, microsecond=0)
        end_time = meeting_time + timedelta(hours=1)
        
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
        appointment.business_id = customer.business_id
        appointment.customer_id = customer.id
        appointment.whatsapp_message_id = whatsapp_message_id
        appointment.title = title
        appointment.description = description
        appointment.start_time = meeting_time
        appointment.end_time = end_time
        appointment.status = 'scheduled'
        appointment.appointment_type = 'viewing'
        appointment.priority = appointment_info['urgency']
        appointment.contact_name = customer.name
        appointment.contact_phone = customer_phone
        appointment.notes = f"נוצרה מווצאפ - ציון: {appointment_info['criteria_score']}/4"
        appointment.auto_generated = True
        appointment.source = 'whatsapp'
        
        db.session.add(appointment)
        db.session.commit()
        
        # 🔥 Add timezone before returning for API responses
        meeting_time_aware = tz.localize(meeting_time)
        
        return {
            'success': True,
            'appointment_id': appointment.id,
            'meeting_time': meeting_time_aware.isoformat(),  # With timezone
            'customer_name': customer.name,
            'title': title,
            'urgency': appointment_info['urgency'],
            'message': f'נוצרה פגישה ל{meeting_time.strftime("%d/%m/%Y בשעה %H:%M")}'
        }
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error creating WhatsApp appointment: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': 'שגיאה ביצירת פגישה מווצאפ'
        }

def send_appointment_confirmation(customer_phone: str, appointment_data: Dict, business_id: int) -> Dict:
    """
    שולח אישור פגישה בווצאפ
    ✅ BUILD 155: Requires business_id - no fallback to prevent cross-tenant issues
    """
    # ✅ BUILD 155 SECURITY: Require explicit business_id
    if not business_id:
        print("❌ send_appointment_confirmation: business_id is required")
        return {'success': False, 'error': 'MISSING_BUSINESS_ID'}
    
    try:
        meeting_time = datetime.fromisoformat(appointment_data['meeting_time'])
        time_str = meeting_time.strftime("%d/%m/%Y בשעה %H:%M")
        
        # ✅ BUILD 154: Get business phone dynamically
        contact_phone_line = ""
        try:
            from server.models_sql import Business
            business = Business.query.get(business_id)
            if business and business.phone_e164:
                display_phone = business.phone_e164
                if display_phone.startswith('+972'):
                    display_phone = '0' + display_phone[4:]
                contact_phone_line = f"\n📞 ליצירת קשר: {display_phone}"
        except Exception as e:
            print(f"⚠️ Could not get business phone: {e}")
        
        # הודעת אישור
        confirmation_message = f"""
🗓️ *פגישה נקבעה בהצלחה!*

📅 תאריך: {time_str}
🏢 נושא: {appointment_data['title']}{contact_phone_line}

נשמח לראותכם! אם יש צורך בשינוי, אנא הודיעו מראש.
        """.strip()
        
        # שליחה דרך API המאוחד - ✅ BUILD 155: Explicit business_id required
        response = requests.post("http://localhost:5000/api/whatsapp/send", json={
            'to': customer_phone,
            'message': confirmation_message,
            'business_id': business_id
        })
        
        if response.status_code == 200:
            return {'success': True, 'message': 'אישור נשלח בווצאפ'}
        else:
            return {'success': False, 'error': 'שגיאה בשליחת אישור'}
            
    except Exception as e:
        print(f"❌ Error sending WhatsApp confirmation: {e}")
        return {'success': False, 'error': str(e)}

def send_appointment_reminder(appointment_id: int) -> Dict:
    """
    שולח תזכורת פגישה בווצאפ (24 שעות לפני)
    """
    try:
        appointment = Appointment.query.get(appointment_id)
        if not appointment or not appointment.contact_phone:
            return {'success': False, 'error': 'פגישה או מספר טלפון לא נמצאו'}
        
        # בדיקה שהפגישה מחר
        now = datetime.now()
        time_until = appointment.start_time - now
        
        if not (timedelta(hours=20) <= time_until <= timedelta(hours=28)):
            return {'success': False, 'error': 'פגישה לא במועד המתאים לתזכורת'}
        
        # יצירת הודעת תזכורת
        meeting_time = appointment.start_time.strftime("%d/%m בשעה %H:%M")
        area = "המשרד" if not appointment.location else appointment.location
        
        reminder_message = f"""
🔔 *תזכורת פגישה*

היי {appointment.contact_name or 'שם לא ידוע'}!

תזכורת לפגישה שלנו מחר ב-{meeting_time}

📍 מיקום: {area}
🏠 נושא: {appointment.title}

האם הזמן עדיין מתאים לכם?
        """.strip()  # ✅ הסרת חתימה hardcoded
        
        # 🔥 HARDENING: Require explicit business_id - no fallback!
        if not appointment.business_id:
            return {'success': False, 'error': 'business_id required for multi-tenant isolation'}
        
        # שליחה
        response = requests.post("http://localhost:5000/api/whatsapp/send", json={
            'to': appointment.contact_phone,
            'message': reminder_message,
            'business_id': appointment.business_id
        })
        
        if response.status_code == 200:
            # עדכון שתזכורת נשלחה
            appointment.notes = (appointment.notes or "") + f"\nתזכורת נשלחה: {now.strftime('%d/%m/%Y %H:%M')}"
            db.session.commit()
            return {'success': True, 'message': 'תזכורת נשלחה בהצלחה'}
        else:
            return {'success': False, 'error': 'שגיאה בשליחת תזכורת'}
            
    except Exception as e:
        print(f"❌ Error sending appointment reminder: {e}")
        return {'success': False, 'error': str(e)}

def process_incoming_whatsapp_message(phone_number: str, message_text: str, message_id: Optional[int] = None, business_id: Optional[int] = None) -> Dict:
    """
    מעבד הודעת ווצאפ נכנסת ובודק האם יש צורך ביצירת פגישה
    
    Args:
        phone_number: מספר טלפון של הלקוח
        message_text: תוכן ההודעה
        message_id: מזהה ההודעה ב-DB
        business_id: מזהה העסק (לשימוש multi-tenant)
    """
    try:
        # חילוץ מידע מההודעה
        appointment_info = extract_appointment_info_from_whatsapp(message_text, phone_number)
        
        result: Dict = {'processed': False, 'appointment_created': False}
        
        # 🔥 HARDENING: Require explicit business_id - no fallback to 1!
        if not business_id:
            print(f"❌ [WA-APPT-ERROR] process_incoming_whatsapp_message: business_id required but not provided")
            return {'processed': False, 'error': 'business_id required for multi-tenant isolation'}
        
        # 🔥 BUILD 200: אם יש בקשה לפגישה אבל לא מספיק מידע - GENERIC message
        if appointment_info['has_request'] and not appointment_info['meeting_ready']:
            # שלח הודעת בקשת מידע נוסף - GENERIC for any business
            missing_info = []
            if not appointment_info['area']:
                missing_info.append('איזה אזור נוח לכם?')
            
            follow_up_message = f"""
תודה על הפנייה!

כדי לקבוע פגישה, אשמח לדעת:
{chr(10).join(f"• {info}" for info in missing_info)}
            """.strip()  # 🔥 BUILD 200: Generic message - works for any business
            
            requests.post("http://localhost:5000/api/whatsapp/send", json={
                'to': phone_number,
                'message': follow_up_message,
                'business_id': business_id  # ✅ FIX: Use correct business_id
            })
            
            result['processed'] = True
            result['follow_up_sent'] = True
        
        # אם יש מספיק מידע - צור פגישה
        elif appointment_info['meeting_ready']:
            appointment_result = create_whatsapp_appointment(phone_number, message_text, message_id, business_id)  # ✅ FIX: Pass business_id
            
            if appointment_result['success']:
                # שלח אישור - ✅ BUILD 155: Pass business_id for multi-tenant safety
                send_appointment_confirmation(phone_number, appointment_result, business_id)
                
                result['processed'] = True
                result['appointment_created'] = True
                result['appointment_id'] = appointment_result['appointment_id']
                result['appointment_details'] = appointment_result
        
        return result
        
    except Exception as e:
        print(f"❌ Error processing WhatsApp message: {e}")
        return {'processed': False, 'error': str(e)}

def get_upcoming_appointments_for_reminders() -> List[Dict]:
    """
    מחזיר רשימת פגישות שזקוקות לתזכורת (24 שעות לפני)
    """
    try:
        now = datetime.now()
        tomorrow_start = now + timedelta(hours=20)  # 20 שעות מעכשיו
        tomorrow_end = now + timedelta(hours=28)    # 28 שעות מעכשיו
        
        appointments = Appointment.query.filter(
            Appointment.start_time.between(tomorrow_start, tomorrow_end),
            Appointment.status.in_(['scheduled', 'confirmed']),
            Appointment.contact_phone.isnot(None)
        ).all()
        
        # סנן רק פגישות שלא נשלחה להן תזכורת
        reminders_needed = []
        for apt in appointments:
            if not apt.notes or 'תזכורת נשלחה:' not in apt.notes:
                # 🔥 Add timezone before returning
                start_time_aware = tz.localize(apt.start_time) if apt.start_time.tzinfo is None else apt.start_time
                reminders_needed.append({
                    'appointment_id': apt.id,
                    'contact_phone': apt.contact_phone,
                    'contact_name': apt.contact_name,
                    'start_time': start_time_aware.isoformat(),  # With timezone
                    'title': apt.title
                })
        
        return reminders_needed
        
    except Exception as e:
        print(f"❌ Error getting appointments for reminders: {e}")
        return []