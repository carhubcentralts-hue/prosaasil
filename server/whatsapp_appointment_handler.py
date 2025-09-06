"""
WhatsApp Appointment Handler - ניהול פגישות דרך וואטסאפ
"""
from datetime import datetime, timedelta
from server.models_sql import Appointment, Customer, Business, WhatsAppMessage, db
from server.whatsapp_templates import send_template_message, select_template
# from server.api_whatsapp_unified import send_message  # לא צריך import ישיר
import re
import json
from typing import Dict, List, Optional
import requests
import os

def extract_appointment_info_from_whatsapp(message_text: str, customer_phone: str) -> Dict:
    """
    מחלץ מידע לפגישה מהודעת ווצאפ
    """
    info = {
        'has_request': False,
        'area': '',
        'property_type': '',
        'budget': '',
        'urgency': 'medium',
        'preferred_time': '',
        'meeting_ready': False
    }
    
    text = message_text.lower()
    
    # זיהוי בקשה לפגישה
    meeting_keywords = [
        'פגישה', 'לראות', 'לצפות', 'לבקר', 'להיפגש',
        'מתי אפשר', 'מתי נוכל', 'אפשר לקבוע', 'בואו נפגש'
    ]
    
    if any(keyword in text for keyword in meeting_keywords):
        info['has_request'] = True
    
    # זיהוי אזור
    area_patterns = {
        'תל אביב': ['תל אביב', 'ת״א', 'דיזנגוף', 'פלורנטין', 'נווה צדק'],
        'רמת גן': ['רמת גן', 'רמ״ג', 'גבעתיים', 'הבורסה'],
        'הרצליה': ['הרצליה', 'פיתוח'],
        'פתח תקווה': ['פתח תקווה', 'פ״ת'],
        'רחובות': ['רחובות'],
        'מודיעין': ['מודיעין'],
        'בית שמש': ['בית שמש'],
        'לוד': ['לוד'],
        'רמלה': ['רמלה'],
        'ירושלים': ['ירושלים', 'יר״ן']
    }
    
    for area, keywords in area_patterns.items():
        if any(keyword in text for keyword in keywords):
            info['area'] = area
            break
    
    # זיהוי סוג נכס
    if re.search(r'\d+\s*חדרים?', text):
        match = re.search(r'(\d+)\s*חדרים?', text)
        if match:
            info['property_type'] = f"דירת {match.group(1)} חדרים"
    elif any(word in text for word in ['דירה', 'בית']):
        info['property_type'] = 'דירה'
    elif 'משרד' in text:
        info['property_type'] = 'משרד'
    
    # זיהוי תקציב
    budget_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:מיליון|אלף|k)', text)
    if budget_match:
        amount = budget_match.group(1)
        unit = 'מיליון' if 'מיליון' in budget_match.group(0) else 'אלף'
        info['budget'] = f"{amount} {unit} ש״ח"
    
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
    
    # החלטה על כשירות לפגישה
    criteria_met = sum([
        bool(info['has_request']),
        bool(info['area']),
        bool(info['property_type']),
        True  # מספר טלפון תמיד קיים
    ])
    
    info['meeting_ready'] = criteria_met >= 3
    info['criteria_score'] = criteria_met
    
    return info

def create_whatsapp_appointment(customer_phone: str, message_text: str, whatsapp_message_id: Optional[int] = None) -> Dict:
    """
    יוצר פגישה מתוך הודעת ווצאפ
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
        
        # חיפוש או יצירת לקוח
        customer = Customer.query.filter_by(phone=customer_phone).first()
        if not customer:
            # יצירת לקוח חדש
            customer = Customer()
            customer.name = f"לקוח מווצאפ {customer_phone[-4:]}"
            customer.phone = customer_phone
            customer.status = "lead"
            
            # קישור לעסק ראשון כברירת מחדל
            business = Business.query.first()
            if business:
                customer.business_id = business.id
            
            db.session.add(customer)
            db.session.flush()
        
        # בניית כותרת ותיאור
        title_parts = [customer.name or f"לקוח {customer_phone[-4:]}"]
        if appointment_info['property_type']:
            title_parts.append(appointment_info['property_type'])
        if appointment_info['area']:
            title_parts.append(f"ב{appointment_info['area']}")
        
        title = " - ".join(title_parts)
        
        description_parts = [
            "פגישה שנוצרה אוטומטית מהודעת ווצאפ:",
            f"הודעה מקורית: {message_text[:100]}..."
        ]
        
        if appointment_info['area']:
            description_parts.append(f"אזור: {appointment_info['area']}")
        if appointment_info['property_type']:
            description_parts.append(f"סוג נכס: {appointment_info['property_type']}")
        if appointment_info['budget']:
            description_parts.append(f"תקציב: {appointment_info['budget']}")
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
        
        return {
            'success': True,
            'appointment_id': appointment.id,
            'meeting_time': meeting_time.isoformat(),
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

def send_appointment_confirmation(customer_phone: str, appointment_data: Dict) -> Dict:
    """
    שולח אישור פגישה בווצאפ
    """
    try:
        meeting_time = datetime.fromisoformat(appointment_data['meeting_time'])
        time_str = meeting_time.strftime("%d/%m/%Y בשעה %H:%M")
        
        # הודעת אישור
        confirmation_message = f"""
🗓️ *פגישה נקבעה בהצלחה!*

📅 תאריך: {time_str}
🏢 נושא: {appointment_data['title']}
📞 ליצירת קשר: 050-1234567

נשמח לראותכם! אם יש צורך בשינוי, אנא הודיעו מראש.

_לאה, שי דירות ומשרדים_
        """.strip()
        
        # שליחה דרך API המאוחד
        response = requests.post("http://localhost:5000/api/whatsapp/send", json={
            'to': customer_phone,
            'message': confirmation_message,
            'business_id': 1
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

_לאה, שי דירות ומשרדים_
        """.strip()
        
        # שליחה
        response = requests.post("http://localhost:5000/api/whatsapp/send", json={
            'to': appointment.contact_phone,
            'message': reminder_message,
            'business_id': appointment.business_id or 1
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

def process_incoming_whatsapp_message(phone_number: str, message_text: str, message_id: Optional[int] = None) -> Dict:
    """
    מעבד הודעת ווצאפ נכנסת ובודק האם יש צורך ביצירת פגישה
    """
    try:
        # חילוץ מידע מההודעה
        appointment_info = extract_appointment_info_from_whatsapp(message_text, phone_number)
        
        result: Dict = {'processed': False, 'appointment_created': False}
        
        # אם יש בקשה לפגישה אבל לא מספיק מידע
        if appointment_info['has_request'] and not appointment_info['meeting_ready']:
            # שלח הודעת בקשת מידע נוסף
            missing_info = []
            if not appointment_info['area']:
                missing_info.append('איזה אזור מעניין אתכם?')
            if not appointment_info['property_type']:
                missing_info.append('איזה סוג נכס אתם מחפשים? (כמה חדרים)')
            
            follow_up_message = f"""
תודה על הפנייה! 🏠

כדי לקבוע פגישה מותאמת אישית, אשמח לדעת:
{chr(10).join(f"• {info}" for info in missing_info)}

זה יעזור לי להכין עבורכם את האפשרויות הטובות ביותר!

_לאה, שי דירות ומשרדים_
            """.strip()
            
            requests.post("http://localhost:5000/api/whatsapp/send", json={
                'to': phone_number,
                'message': follow_up_message,
                'business_id': 1
            })
            
            result['processed'] = True
            result['follow_up_sent'] = True
        
        # אם יש מספיק מידע - צור פגישה
        elif appointment_info['meeting_ready']:
            appointment_result = create_whatsapp_appointment(phone_number, message_text, message_id)
            
            if appointment_result['success']:
                # שלח אישור
                send_appointment_confirmation(phone_number, appointment_result)
                
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
                reminders_needed.append({
                    'appointment_id': apt.id,
                    'contact_phone': apt.contact_phone,
                    'contact_name': apt.contact_name,
                    'start_time': apt.start_time.isoformat(),
                    'title': apt.title
                })
        
        return reminders_needed
        
    except Exception as e:
        print(f"❌ Error getting appointments for reminders: {e}")
        return []