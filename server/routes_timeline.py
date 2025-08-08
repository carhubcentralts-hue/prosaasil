"""
AgentLocator v42 - Timeline API
מערכת איחוד timeline של כל האירועים עבור לקוח
"""

from flask import Blueprint, jsonify, request
import logging
from datetime import datetime
from utils import get_db_connection

logger = logging.getLogger(__name__)
timeline_bp = Blueprint('timeline', __name__)

@timeline_bp.route('/customers/<int:customer_id>/timeline', methods=['GET'])
def get_customer_timeline(customer_id):
    """קבלת timeline מאוחד עבור לקוח - שיחות, הודעות, משימות, חוזים, חשבוניות"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        events = []
        
        # שיחות
        try:
            cur.execute("""
                SELECT 'call' as type, id, created_at, 
                       duration, transcription, ai_response, status
                FROM call_logs 
                WHERE customer_id = %s 
                ORDER BY created_at DESC
            """, (customer_id,))
            
            for row in cur.fetchall():
                events.append({
                    'type': row[0],
                    'id': row[1], 
                    'timestamp': row[2].isoformat() if row[2] else None,
                    'duration': row[3],
                    'transcription': row[4],
                    'ai_response': row[5],
                    'status': row[6],
                    'title': 'שיחה טלפונית',
                    'description': f'משך: {row[3]} שניות' if row[3] else 'שיחה קצרה'
                })
        except Exception as e:
            logger.warning(f"Error fetching calls for customer {customer_id}: {e}")
        
        # הודעות WhatsApp
        try:
            cur.execute("""
                SELECT 'whatsapp' as type, id, created_at,
                       message_content, direction, message_type
                FROM whatsapp_messages
                WHERE customer_id = %s
                ORDER BY created_at DESC
            """, (customer_id,))
            
            for row in cur.fetchall():
                events.append({
                    'type': row[0],
                    'id': row[1],
                    'timestamp': row[2].isoformat() if row[2] else None,
                    'content': row[3],
                    'direction': row[4],  # inbound/outbound
                    'message_type': row[5],
                    'title': 'הודעת WhatsApp',
                    'description': f'{row[4]} - {row[5]}' 
                })
        except Exception as e:
            logger.warning(f"Error fetching WhatsApp messages for customer {customer_id}: {e}")
        
        # משימות
        try:
            cur.execute("""
                SELECT 'task' as type, id, created_at,
                       title, description, status, priority, due_date
                FROM tasks
                WHERE customer_id = %s
                ORDER BY created_at DESC
            """, (customer_id,))
            
            for row in cur.fetchall():
                events.append({
                    'type': row[0],
                    'id': row[1],
                    'timestamp': row[2].isoformat() if row[2] else None,
                    'title': row[3] or 'משימה',
                    'description': row[4],
                    'status': row[5],
                    'priority': row[6],
                    'due_date': row[7].isoformat() if row[7] else None
                })
        except Exception as e:
            logger.warning(f"Error fetching tasks for customer {customer_id}: {e}")
            
        # חוזים
        try:
            cur.execute("""
                SELECT 'contract' as type, id, created_at,
                       title, status, total_amount, start_date, end_date
                FROM contracts
                WHERE customer_id = %s
                ORDER BY created_at DESC
            """, (customer_id,))
            
            for row in cur.fetchall():
                events.append({
                    'type': row[0],
                    'id': row[1],
                    'timestamp': row[2].isoformat() if row[2] else None,
                    'title': row[3] or 'חוזה',
                    'status': row[4],
                    'amount': float(row[5]) if row[5] else 0,
                    'start_date': row[6].isoformat() if row[6] else None,
                    'end_date': row[7].isoformat() if row[7] else None,
                    'description': f'סכום: ₪{row[5]} - {row[4]}'
                })
        except Exception as e:
            logger.warning(f"Error fetching contracts for customer {customer_id}: {e}")
            
        # חשבוניות
        try:
            cur.execute("""
                SELECT 'invoice' as type, id, created_at,
                       invoice_number, status, amount, due_date
                FROM invoices
                WHERE customer_id = %s
                ORDER BY created_at DESC
            """, (customer_id,))
            
            for row in cur.fetchall():
                events.append({
                    'type': row[0],
                    'id': row[1],
                    'timestamp': row[2].isoformat() if row[2] else None,
                    'invoice_number': row[3],
                    'status': row[4],
                    'amount': float(row[5]) if row[5] else 0,
                    'due_date': row[6].isoformat() if row[6] else None,
                    'title': f'חשבונית #{row[3]}',
                    'description': f'סכום: ₪{row[5]} - {row[4]}'
                })
        except Exception as e:
            logger.warning(f"Error fetching invoices for customer {customer_id}: {e}")
        
        cur.close()
        conn.close()
        
        # מיון לפי זמן (החדש ביותר קודם)
        events.sort(key=lambda x: x['timestamp'] or '', reverse=True)
        
        # הגבלה ל-100 אירועים אחרונים
        events = events[:100]
        
        return jsonify({
            'customer_id': customer_id,
            'events': events,
            'total_events': len(events)
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching customer timeline: {e}")
        return jsonify({'error': 'Failed to fetch timeline'}), 500

@timeline_bp.route('/customers/<int:customer_id>/timeline/<event_type>', methods=['GET']) 
def get_customer_timeline_by_type(customer_id, event_type):
    """קבלת timeline מסונן לפי סוג אירוע"""
    try:
        # קבלת כל האירועים
        response = get_customer_timeline(customer_id)
        if response[1] != 200:
            return response
            
        data = response[0].get_json()
        
        # סינון לפי סוג
        filtered_events = [
            event for event in data['events'] 
            if event['type'] == event_type
        ]
        
        return jsonify({
            'customer_id': customer_id,
            'event_type': event_type,
            'events': filtered_events,
            'total_events': len(filtered_events)
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching timeline by type: {e}")
        return jsonify({'error': 'Failed to fetch filtered timeline'}), 500