"""
Customer Intelligence API Routes
מסלולי API למערכת אינטליגנציה לקוחות
"""
from flask import Blueprint, jsonify, request
from server.extensions import csrf
from server.auth_api import require_api_auth
from server.models_sql import Customer, Lead, CallLog, Business
from server.db import db
from sqlalchemy import func, desc, case
from sqlalchemy.orm import aliased
from datetime import datetime, timedelta

intelligence_bp = Blueprint('intelligence', __name__, url_prefix='/api/intelligence')

@intelligence_bp.route('/customers', methods=['GET'])
@require_api_auth(['business', 'admin', 'manager'])
def get_intelligent_customers():
    """
    קבלת רשימת לקוחות עם נתוני אינטליגנציה
    """
    try:
        # אמינות: בדיקה חמורה של business_id
        business_id = getattr(request, 'business_id', None)
        if not business_id:
            return jsonify({'error': 'Business context required'}), 400
        source_filter = request.args.get('source', 'all')
        sort_by = request.args.get('sort', 'recent')
        
        # בסיס השאילתה
        query = db.session.query(Customer).filter_by(business_id=business_id)
        
        # סינון לפי מקור (אם יש שדה source)
        if source_filter != 'all' and hasattr(Customer, 'source'):
            query = query.filter(Customer.source == source_filter)
        
        # מיון
        if sort_by == 'recent':
            query = query.order_by(desc(Customer.created_at))
        elif sort_by == 'leads':
            # מיון לפי מספר לידים (אם יש שדה customer_id)
            if hasattr(Lead, 'customer_id'):
                leads_count = db.session.query(
                    Lead.customer_id,
                    func.count(Lead.id).label('count')
                ).filter_by(business_id=business_id).group_by(Lead.customer_id).subquery()
                
                query = query.outerjoin(leads_count, Customer.id == leads_count.c.customer_id)\
                             .order_by(desc(leads_count.c.count))
            else:
                # Fallback to date sorting if no customer_id
                query = query.order_by(desc(Customer.created_at))
            
        else:  # name
            query = query.order_by(Customer.name)
        
        customers = query.limit(50).all()
        
        # 🔥 PERFORMANCE FIX: Single aggregated query instead of N+1 (4 queries per customer)
        # Build aggregated data for all customers in ONE query using subqueries
        customer_phones = [c.phone_e164 for c in customers if c.phone_e164]
        
        # Subquery 1: Count leads per phone
        leads_counts_subq = db.session.query(
            Lead.phone_e164,
            func.count(Lead.id).label('leads_count')
        ).filter(
            Lead.tenant_id == business_id,
            Lead.phone_e164.in_(customer_phones)
        ).group_by(Lead.phone_e164).subquery()
        
        # Subquery 2: Count calls per phone
        calls_counts_subq = db.session.query(
            CallLog.from_number,
            func.count(CallLog.id).label('calls_count')
        ).filter(
            CallLog.business_id == business_id,
            CallLog.from_number.in_(customer_phones)
        ).group_by(CallLog.from_number).subquery()
        
        # Subquery 3: Get latest lead per phone (using window function for efficiency)
        from sqlalchemy import select
        latest_lead_subq = db.session.query(
            Lead.phone_e164,
            Lead.id.label('latest_lead_id'),
            Lead.status,
            Lead.area,
            Lead.property_type,
            Lead.notes,
            Lead.created_at,
            Lead.updated_at,
            func.row_number().over(
                partition_by=Lead.phone_e164,
                order_by=desc(Lead.created_at)
            ).label('rn')
        ).filter(
            Lead.tenant_id == business_id,
            Lead.phone_e164.in_(customer_phones)
        ).subquery()
        
        # Filter to get only the latest lead (rn = 1)
        latest_leads_filtered = db.session.query(
            latest_lead_subq
        ).filter(
            latest_lead_subq.c.rn == 1
        ).subquery()
        
        # Subquery 4: Get last call per phone (using window function)
        last_call_subq = db.session.query(
            CallLog.from_number,
            CallLog.id.label('last_call_id'),
            CallLog.status,
            CallLog.transcription,
            CallLog.created_at,
            func.row_number().over(
                partition_by=CallLog.from_number,
                order_by=desc(CallLog.created_at)
            ).label('rn')
        ).filter(
            CallLog.business_id == business_id,
            CallLog.from_number.in_(customer_phones)
        ).subquery()
        
        # Filter to get only the last call (rn = 1)
        last_calls_filtered = db.session.query(
            last_call_subq
        ).filter(
            last_call_subq.c.rn == 1
        ).subquery()
        
        # Execute all subqueries and build lookup dictionaries
        leads_counts = {row.phone_e164: row.leads_count 
                       for row in db.session.query(leads_counts_subq).all()}
        calls_counts = {row.from_number: row.calls_count 
                       for row in db.session.query(calls_counts_subq).all()}
        latest_leads_map = {row.phone_e164: row 
                           for row in db.session.query(latest_leads_filtered).all()}
        last_calls_map = {row.from_number: row 
                         for row in db.session.query(last_calls_filtered).all()}
        
        # בניית תגובה עם נתונים מורחבים
        result = []
        for customer in customers:
            phone = customer.phone_e164
            
            # Get aggregated data from lookup dictionaries (O(1) lookups)
            leads_count = leads_counts.get(phone, 0)
            calls_count = calls_counts.get(phone, 0)
            latest_lead_data = latest_leads_map.get(phone)
            last_call_data = last_calls_map.get(phone)
            
            # Construct lead object from subquery data if available
            latest_lead = None
            if latest_lead_data:
                # Create a mock object with the necessary attributes
                class LatestLeadProxy:
                    def __init__(self, data):
                        self.id = data.latest_lead_id
                        self.status = data.status
                        self.area = data.area
                        self.property_type = data.property_type
                        self.notes = data.notes
                        self.created_at = data.created_at
                        self.updated_at = data.updated_at
                latest_lead = LatestLeadProxy(latest_lead_data)
            
            # Construct call object from subquery data if available
            last_call = None
            if last_call_data:
                # Create a mock object with the necessary attributes
                class LastCallProxy:
                    def __init__(self, data):
                        self.id = data.last_call_id
                        self.status = data.status
                        self.transcription = data.transcription
                        self.created_at = data.created_at
                last_call = LastCallProxy(last_call_data)
            
            last_interaction = customer.created_at
            if last_call and last_call.created_at > last_interaction:
                last_interaction = last_call.created_at
            if latest_lead and latest_lead.updated_at and latest_lead.updated_at > last_interaction:
                last_interaction = latest_lead.updated_at
            
            # בניית פעילויות אחרונות
            recent_activity = []
            if last_call:
                recent_activity.append({
                    'type': 'call',
                    'timestamp': last_call.created_at.isoformat() if last_call.created_at else '',
                    'content': f"שיחה טלפונית • {last_call.status}",
                    'ai_summary': last_call.transcription[:100] + '...' if last_call.transcription else None
                })
            
            if latest_lead:
                recent_activity.append({
                    'type': 'lead_update',
                    'timestamp': latest_lead.updated_at.isoformat() if latest_lead.updated_at else latest_lead.created_at.isoformat(),
                    'content': f"עדכון ליד • {latest_lead.status}",
                    'ai_summary': latest_lead.notes[:100] + '...' if latest_lead.notes else None
                })
            
            customer_data = {
                'id': customer.id,
                'name': customer.name,
                'phone_e164': customer.phone_e164,
                'source': getattr(customer, 'source', 'manual'),
                'created_at': customer.created_at.isoformat() if customer.created_at else '',
                'last_interaction': last_interaction.isoformat() if last_interaction else '',
                'leads_count': leads_count,
                'calls_count': calls_count,
                'whatsapp_count': 0,  # TODO: הוסף ספירת WhatsApp כשתהיה טבלה
                'recent_activity': sorted(recent_activity, key=lambda x: x['timestamp'], reverse=True)[:3]
            }
            
            # פרטי ליד אחרון
            if latest_lead:
                customer_data['latest_lead'] = {
                    'id': latest_lead.id,
                    'status': latest_lead.status or 'חדש',
                    'area': latest_lead.area,
                    'property_type': latest_lead.property_type,
                    'notes': latest_lead.notes,
                    'ai_summary': _generate_ai_summary_for_lead(latest_lead),
                    'intent': _extract_intent_from_notes(latest_lead.notes) if latest_lead.notes else None,
                    'next_action': _suggest_next_action(latest_lead)
                }
            
            result.append(customer_data)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch customers: {str(e)}'}), 500

@intelligence_bp.route('/stats', methods=['GET'])
@require_api_auth(['business', 'admin', 'manager'])
def get_intelligence_stats():
    """
    קבלת סטטיסטיקות אינטליגנציה
    """
    try:
        # אמינות: בדיקה חמורה של business_id
        business_id = getattr(request, 'business_id', None)
        if not business_id:
            return jsonify({'error': 'Business context required'}), 400
        today = datetime.utcnow().date()
        
        # סטטיסטיקות בסיסיות
        total_customers = Customer.query.filter_by(business_id=business_id).count()
        new_customers_today = Customer.query.filter_by(business_id=business_id)\
            .filter(func.date(Customer.created_at) == today).count()
        
        total_leads = Lead.query.filter_by(tenant_id=business_id).count()
        new_leads_today = Lead.query.filter_by(tenant_id=business_id)\
            .filter(func.date(Lead.created_at) == today).count()
        
        # חישוב שיעורי המרה
        total_calls = CallLog.query.filter_by(business_id=business_id).count()
        call_conversion_rate = round((total_leads / total_calls * 100) if total_calls > 0 else 0, 1)
        
        # WhatsApp conversion (placeholder)
        whatsapp_conversion_rate = 75  # TODO: חשב בפועל כשתהיה מידע
        
        # לידים מוכנים לפגישה
        meeting_ready_leads = Lead.query.filter_by(tenant_id=business_id)\
            .filter(Lead.status.in_(['מוכשר', 'מוכן לפגישה'])).count()
        
        # אינטראקציות שעובדו על ידי AI
        ai_processed_interactions = CallLog.query.filter_by(business_id=business_id)\
            .filter(CallLog.transcription.isnot(None)).count()
        
        stats = {
            'total_customers': total_customers,
            'new_customers_today': new_customers_today,
            'total_leads': total_leads,
            'new_leads_today': new_leads_today,
            'call_conversion_rate': call_conversion_rate,
            'whatsapp_conversion_rate': whatsapp_conversion_rate,
            'ai_processed_interactions': ai_processed_interactions,
            'meeting_ready_leads': meeting_ready_leads
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch stats: {str(e)}'}), 500

def _generate_ai_summary_for_lead(lead):
    """יצירת סיכום AI בסיסי לליד"""
    if not lead.notes:
        return "אין מידע זמין"
    
    notes = lead.notes.lower()
    
    # זיהוי כוונות בסיסי
    if 'פגישה' in notes:
        return "הלקוח מעוניין בתיאום פגישה"
    elif 'לא מעוניין' in notes:
        return "הלקוח הביע חוסר עניין"
    elif 'תקציב' in notes:
        return "נדון תקציב ודרישות"
    elif 'חזרה' in notes or 'התקשר' in notes:
        return "נדרש מעקב טלפוני"
    else:
        return f"אינטראקציה של {len(lead.notes)} תווים"

def _extract_intent_from_notes(notes):
    """חילוץ כוונה מתוך ההערות"""
    if not notes:
        return None
    
    notes_lower = notes.lower()
    
    if 'קנייה' in notes_lower or 'לקנות' in notes_lower:
        return 'רכישה'
    elif 'השכרה' in notes_lower or 'לשכור' in notes_lower:
        return 'השכרה'
    elif 'מכירה' in notes_lower or 'למכור' in notes_lower:
        return 'מכירה'
    elif 'השקעה' in notes_lower:
        return 'השקעה'
    else:
        return 'כללי'

def _suggest_next_action(lead):
    """הצעת פעולה הבאה"""
    if not lead:
        return "יצירת קשר ראשוני"
    
    status = lead.status.lower() if lead.status else ''
    notes = lead.notes.lower() if lead.notes else ''
    
    if 'חדש' in status:
        return "יצירת קשר ראשוני"
    elif 'בניסיון קשר' in status:
        return "המשך ניסיונות קשר"
    elif 'נוצר קשר' in status:
        if 'פגישה' in notes:
            return "תיאום פגישה לצפייה"
        else:
            return "זיהוי צרכים ודרישות"
    elif 'מוכשר' in status:
        return "הצגת אפשרויות מתאימות"
    else:
        return "מעקב ועדכון סטטוס"