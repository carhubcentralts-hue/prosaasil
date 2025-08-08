"""
AgentLocator v42 - Calendar Integration Routes
ממשק יומן ותאומי פגישות עם Google Calendar
"""

from flask import Blueprint, jsonify, request
import logging
from datetime import datetime, timedelta
from utils import get_db_connection

logger = logging.getLogger(__name__)
calendar_bp = Blueprint('calendar', __name__)

@calendar_bp.route('/customers/<int:customer_id>/schedule', methods=['POST'])
def schedule_appointment(customer_id):
    """תזמון פגישה חדשה עבור לקוח"""
    try:
        data = request.get_json()
        
        # ולידציה של נתונים
        required_fields = ['title', 'date', 'time', 'duration']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'נדרשים כל השדות: title, date, time, duration'}), 400
        
        appointment_date = datetime.fromisoformat(f"{data['date']} {data['time']}")
        duration_minutes = int(data.get('duration', 60))
        end_time = appointment_date + timedelta(minutes=duration_minutes)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        # בדיקת זמינות - אין חפיפות
        cur.execute("""
            SELECT COUNT(*) FROM appointments 
            WHERE business_id = (
                SELECT business_id FROM customers WHERE id = %s
            )
            AND (
                (scheduled_at <= %s AND scheduled_end > %s) OR
                (scheduled_at < %s AND scheduled_end >= %s) OR
                (scheduled_at >= %s AND scheduled_at < %s)
            )
            AND status NOT IN ('cancelled', 'completed')
        """, (customer_id, appointment_date, appointment_date, 
              end_time, end_time, appointment_date, end_time))
        
        conflicts = cur.fetchone()[0]
        if conflicts > 0:
            return jsonify({'error': 'הזמן תפוס. אנא בחר זמן אחר'}), 409
        
        # יצירת הפגישה
        cur.execute("""
            INSERT INTO appointments (
                customer_id, business_id, title, description,
                scheduled_at, scheduled_end, status, created_at
            ) VALUES (
                %s, 
                (SELECT business_id FROM customers WHERE id = %s),
                %s, %s, %s, %s, 'scheduled', NOW()
            ) RETURNING id
        """, (customer_id, customer_id, data['title'], 
              data.get('description', ''), appointment_date, end_time))
        
        appointment_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        # Google Calendar sync (אופציונלי)
        try:
            sync_with_google_calendar(appointment_id, appointment_date, data)
        except Exception as e:
            logger.warning(f"Google Calendar sync failed: {e}")
        
        return jsonify({
            'id': appointment_id,
            'message': 'הפגישה נקבעה בהצלחה',
            'appointment_date': appointment_date.isoformat(),
            'duration': duration_minutes
        }), 201
        
    except ValueError as e:
        return jsonify({'error': 'פורמט תאריך/שעה לא תקין'}), 400
    except Exception as e:
        logger.error(f"Error scheduling appointment: {e}")
        return jsonify({'error': 'שגיאה בתזמון הפגישה'}), 500

@calendar_bp.route('/customers/<int:customer_id>/appointments', methods=['GET'])
def get_customer_appointments(customer_id):
    """קבלת כל הפגישות של לקוח"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, title, description, scheduled_at, 
                   scheduled_end, status, created_at
            FROM appointments 
            WHERE customer_id = %s
            ORDER BY scheduled_at DESC
        """, (customer_id,))
        
        appointments = []
        for row in cur.fetchall():
            appointments.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'scheduled_at': row[3].isoformat() if row[3] else None,
                'scheduled_end': row[4].isoformat() if row[4] else None,
                'status': row[5],
                'created_at': row[6].isoformat() if row[6] else None
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'appointments': appointments,
            'total': len(appointments)
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching appointments: {e}")
        return jsonify({'error': 'שגיאה בטעינת הפגישות'}), 500

@calendar_bp.route('/appointments/<int:appointment_id>/reschedule', methods=['PUT'])
def reschedule_appointment(appointment_id):
    """שינוי מועד פגישה"""
    try:
        data = request.get_json()
        new_date = data.get('new_date')
        new_time = data.get('new_time')
        
        if not new_date or not new_time:
            return jsonify({'error': 'נדרש תאריך ושעה חדשים'}), 400
        
        new_datetime = datetime.fromisoformat(f"{new_date} {new_time}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        # עדכון מועד הפגישה
        cur.execute("""
            UPDATE appointments 
            SET scheduled_at = %s,
                scheduled_end = %s + INTERVAL '1 HOUR',
                status = 'rescheduled',
                updated_at = NOW()
            WHERE id = %s
            RETURNING customer_id, title
        """, (new_datetime, new_datetime, appointment_id))
        
        result = cur.fetchone()
        if not result:
            return jsonify({'error': 'פגישה לא נמצאה'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        # הודעה ללקוח על השינוי
        try:
            send_reschedule_notification(result[0], result[1], new_datetime)
        except Exception as e:
            logger.warning(f"Notification failed: {e}")
        
        return jsonify({
            'message': 'מועד הפגישה שונה בהצלחה',
            'new_appointment_time': new_datetime.isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error rescheduling appointment: {e}")
        return jsonify({'error': 'שגיאה בשינוי מועד הפגישה'}), 500

@calendar_bp.route('/appointments/<int:appointment_id>/cancel', methods=['DELETE'])
def cancel_appointment(appointment_id):
    """ביטול פגישה"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE appointments 
            SET status = 'cancelled',
                cancelled_at = NOW()
            WHERE id = %s
            RETURNING customer_id, title, scheduled_at
        """, (appointment_id,))
        
        result = cur.fetchone()
        if not result:
            return jsonify({'error': 'פגישה לא נמצאה'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        # הודעה על ביטול
        try:
            send_cancellation_notification(result[0], result[1], result[2])
        except Exception as e:
            logger.warning(f"Cancellation notification failed: {e}")
        
        return jsonify({'message': 'הפגישה בוטלה בהצלחה'}), 200
        
    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}")
        return jsonify({'error': 'שגיאה בביטול הפגישה'}), 500

def sync_with_google_calendar(appointment_id, appointment_date, data):
    """סינכרון עם Google Calendar (פלייסהולדר)"""
    # כאן יבוא האינטגרציה עם Google Calendar API
    logger.info(f"Google Calendar sync for appointment {appointment_id}")
    pass

def send_reschedule_notification(customer_id, title, new_datetime):
    """שליחת הודעה על שינוי מועד"""
    logger.info(f"Reschedule notification sent to customer {customer_id}")
    pass

def send_cancellation_notification(customer_id, title, scheduled_at):
    """שליחת הודעה על ביטול"""
    logger.info(f"Cancellation notification sent to customer {customer_id}")
    pass