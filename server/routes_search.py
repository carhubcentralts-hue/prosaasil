"""
Global Search API - searches across leads, calls, WhatsApp, and contacts
Supports multi-tenant with business_id filtering
"""
from flask import Blueprint, request, jsonify, session
from server.auth_api import require_api_auth
from server.db import db
from server.models_sql import Lead, CallLog, WhatsAppConversation, User, Business
from sqlalchemy import or_, and_, func
from datetime import datetime
import logging

log = logging.getLogger(__name__)

search_api = Blueprint('search_api', __name__, url_prefix='/api')


@search_api.route('/search', methods=['GET'])
@require_api_auth()
def global_search():
    """
    Global search across all system entities
    
    Query params:
    - q: search query (required, min 2 chars)
    - types: comma-separated list of types to search (optional)
            valid types: leads, calls, whatsapp, contacts
    - limit: max results per type (default: 5)
    
    Returns:
    {
      "query": "search term",
      "results": {
        "leads": [...],
        "calls": [...],
        "whatsapp": [...],
        "contacts": [...]
      },
      "total": 15
    }
    """
    try:
        # Get current user and business context
        user = session.get('al_user') or session.get('user', {})
        user_role = user.get('role')
        
        # Get business_id based on role
        if user_role == 'system_admin':
            # System admin can search across all businesses or filter by business_id
            business_id = request.args.get('business_id', type=int)
        else:
            # Regular users can only search within their business
            business_id = session.get('impersonated_tenant_id') or user.get('business_id')
        
        if not business_id:
            return jsonify({'error': 'Business context required'}), 401
        
        # Get search parameters
        query = request.args.get('q', '').strip()
        if len(query) < 2:
            return jsonify({
                'query': query,
                'results': {
                    'leads': [],
                    'calls': [],
                    'whatsapp': [],
                    'contacts': [],
                    'pages': [],
                    'settings': []
                },
                'total': 0
            })
        
        # Sanitize query - prevent special SQL characters
        # SQLAlchemy's ilike() uses parameterized queries, but we sanitize for extra safety
        query = query.replace('%', '').replace('_', '').replace('\\', '')[:100]  # Max 100 chars
        
        # Parse types filter
        types_param = request.args.get('types', 'all')
        if types_param == 'all':
            search_types = ['leads', 'calls', 'whatsapp', 'contacts', 'pages', 'settings']
        else:
            search_types = [t.strip() for t in types_param.split(',')]
        limit = request.args.get('limit', 5, type=int)
        
        results = {
            'leads': [],
            'calls': [],
            'whatsapp': [],
            'contacts': [],
            'pages': [],
            'settings': []
        }
        
        # Search in Leads
        if 'leads' in search_types:
            try:
                # Search by name, phone, email, or notes
                leads_query = Lead.query.filter(
                    Lead.business_id == business_id,
                    or_(
                        Lead.name.ilike(f'%{query}%'),
                        Lead.phone.ilike(f'%{query}%'),
                        Lead.email.ilike(f'%{query}%'),
                        Lead.notes.ilike(f'%{query}%')
                    )
                ).order_by(Lead.created_at.desc()).limit(limit)
                
                for lead in leads_query.all():
                    results['leads'].append({
                        'id': lead.id,
                        'type': 'lead',
                        'title': lead.name or 'לא ידוע',
                        'subtitle': lead.phone or lead.email,
                        'description': lead.notes or '',
                        'metadata': {
                            'phone': lead.phone,
                            'email': lead.email,
                            'status': lead.status or 'חדש',
                            'created_at': lead.created_at.isoformat() if lead.created_at else None,
                            'source': lead.source
                        }
                    })
            except Exception as e:
                log.error(f"Error searching leads: {e}")
        
        # Search in Calls
        if 'calls' in search_types:
            try:
                # Search by phone number or call SID
                calls_query = CallLog.query.filter(
                    CallLog.business_id == business_id,
                    or_(
                        CallLog.from_number.ilike(f'%{query}%'),
                        CallLog.to_number.ilike(f'%{query}%'),
                        CallLog.call_sid.ilike(f'%{query}%')
                    )
                ).order_by(CallLog.created_at.desc()).limit(limit)
                
                for call in calls_query.all():
                    # Get lead info if exists
                    lead_name = None
                    if call.lead_id:
                        lead = Lead.query.get(call.lead_id)
                        if lead:
                            lead_name = lead.name
                    
                    results['calls'].append({
                        'id': call.id,
                        'type': 'call',
                        'title': f"שיחה עם {lead_name or call.from_number or call.to_number}",
                        'subtitle': call.from_number or call.to_number,
                        'description': f"כיוון: {call.direction or 'לא ידוע'}, משך: {call.duration or 0} שניות",
                        'metadata': {
                            'phone': call.from_number if call.direction == 'inbound' else call.to_number,
                            'direction': call.direction,
                            'duration': call.duration,
                            'status': call.status,
                            'created_at': call.created_at.isoformat() if call.created_at else None,
                            'lead_id': call.lead_id
                        }
                    })
            except Exception as e:
                log.error(f"Error searching calls: {e}")
        
        # Search in WhatsApp Conversations
        if 'whatsapp' in search_types:
            try:
                # Search by phone or customer name
                conversations_query = WhatsAppConversation.query.filter(
                    WhatsAppConversation.business_id == business_id,
                    or_(
                        WhatsAppConversation.customer_number.ilike(f'%{query}%'),
                        WhatsAppConversation.customer_name.ilike(f'%{query}%')
                    )
                ).order_by(WhatsAppConversation.last_message_at.desc()).limit(limit)
                
                for conversation in conversations_query.all():
                    results['whatsapp'].append({
                        'id': conversation.id,
                        'type': 'whatsapp',
                        'title': f"WhatsApp - {conversation.customer_name or conversation.customer_number}",
                        'subtitle': conversation.customer_number,
                        'description': f"סטטוס: {'פתוח' if conversation.is_open else 'סגור'}",
                        'metadata': {
                            'phone': conversation.customer_number,
                            'customer_name': conversation.customer_name,
                            'last_activity': conversation.last_message_at.isoformat() if conversation.last_message_at else None,
                            'is_open': conversation.is_open,
                            'lead_id': conversation.lead_id
                        }
                    })
            except Exception as e:
                log.error(f"Error searching WhatsApp conversations: {e}")
        
        # Search in Contacts/Users (optional - for internal team search)
        if 'contacts' in search_types:
            try:
                # Search users in the same business
                users_query = User.query.filter(
                    User.business_id == business_id,
                    or_(
                        User.name.ilike(f'%{query}%'),
                        User.email.ilike(f'%{query}%')
                    )
                ).order_by(User.created_at.desc()).limit(limit)
                
                for user in users_query.all():
                    results['contacts'].append({
                        'id': user.id,
                        'type': 'contact',
                        'title': user.name or user.email,
                        'subtitle': user.email,
                        'description': f"תפקיד: {user.role}",
                        'metadata': {
                            'email': user.email,
                            'role': user.role,
                            'is_active': user.is_active,
                            'last_login': user.last_login.isoformat() if user.last_login else None
                        }
                    })
            except Exception as e:
                log.error(f"Error searching contacts: {e}")
        
        # Search in System Pages (דפים במערכת)
        if 'pages' in search_types or types_param == 'all' or not types_param:
            SYSTEM_PAGES = [
                {'id': 'leads', 'title': 'לידים', 'description': 'ניהול לידים ולקוחות', 'keywords': ['לידים', 'לקוחות', 'leads', 'crm'], 'path': '/app/leads', 'category': 'ניהול'},
                {'id': 'calls', 'title': 'שיחות טלפון', 'description': 'שיחות נכנסות ויוצאות', 'keywords': ['שיחות', 'טלפון', 'calls'], 'path': '/app/calls', 'category': 'תקשורת'},
                {'id': 'inbound', 'title': 'שיחות נכנסות', 'description': 'שיחות נכנסות', 'keywords': ['נכנס', 'inbound'], 'path': '/app/calls', 'category': 'תקשורת'},
                {'id': 'outbound', 'title': 'שיחות יוצאות', 'description': 'שיחות יוצאות', 'keywords': ['יוצא', 'outbound'], 'path': '/app/outbound-calls', 'category': 'תקשורת'},
                {'id': 'whatsapp', 'title': 'WhatsApp', 'description': 'שיחות WhatsApp', 'keywords': ['whatsapp', 'ווצאפ'], 'path': '/app/whatsapp', 'category': 'תקשורת'},
                {'id': 'broadcast', 'title': 'תפוצת WhatsApp', 'description': 'שלח הודעות המוניות', 'keywords': ['תפוצה', 'broadcast'], 'path': '/app/whatsapp-broadcast', 'category': 'תקשורת'},
                {'id': 'crm', 'title': 'משימות', 'description': 'ניהול משימות', 'keywords': ['משימות', 'tasks', 'crm'], 'path': '/app/crm', 'category': 'ניהול'},
                {'id': 'users', 'title': 'ניהול משתמשים', 'description': 'ניהול משתמשים והרשאות', 'keywords': ['משתמשים', 'users'], 'path': '/app/users', 'category': 'הגדרות'},
                {'id': 'settings', 'title': 'הגדרות מערכת', 'description': 'הגדרות כלליות', 'keywords': ['הגדרות', 'settings'], 'path': '/app/settings', 'category': 'הגדרות'},
                {'id': 'businesses', 'title': 'ניהול עסקים', 'description': 'ניהול עסקים (מנהל מערכת)', 'keywords': ['עסקים', 'businesses'], 'path': '/app/admin/businesses', 'category': 'ניהול', 'roles': ['system_admin']},
            ]
            
            query_lower = query.lower()
            for page in SYSTEM_PAGES:
                # Check role access
                if 'roles' in page and user_role not in page.get('roles', []):
                    continue
                
                # Search in title, description, keywords
                if (query_lower in page['title'].lower() or
                    query_lower in page['description'].lower() or
                    any(query_lower in kw.lower() for kw in page['keywords'])):
                    results['pages'].append({
                        'id': page['id'],
                        'type': 'function',
                        'title': page['title'],
                        'subtitle': page['category'],
                        'description': page['description'],
                        'metadata': {
                            'path': page['path'],
                            'category': page['category']
                        }
                    })
        
        # Search in Settings (הגדרות)
        if 'settings' in search_types or types_param == 'all' or not types_param:
            SYSTEM_SETTINGS = [
                {'id': 'webhook', 'title': 'Webhook', 'description': 'הגדרות Webhook ל-Twilio', 'keywords': ['webhook', 'twilio'], 'path': '/app/settings', 'section': 'integrations'},
                {'id': 'ai-prompts', 'title': 'AI Prompts', 'description': 'הגדרות פרומפטים ל-AI', 'keywords': ['ai', 'prompts', 'בינה מלאכותית'], 'path': '/app/settings', 'section': 'ai'},
                {'id': 'phone', 'title': 'מספרי טלפון', 'description': 'ניהול מספרי טלפון', 'keywords': ['טלפון', 'phone', 'numbers'], 'path': '/app/settings', 'section': 'phone'},
                {'id': 'whatsapp-config', 'title': 'הגדרות WhatsApp', 'description': 'Meta Cloud API / Baileys', 'keywords': ['whatsapp', 'meta', 'baileys'], 'path': '/app/settings', 'section': 'whatsapp'},
                {'id': 'statuses', 'title': 'ניהול סטטוסים', 'description': 'ניהול סטטוסים של לידים', 'keywords': ['סטטוסים', 'statuses', 'pipeline'], 'path': '/app/leads', 'action': 'open-status-modal'},
            ]
            
            query_lower = query.lower()
            for setting in SYSTEM_SETTINGS:
                # Search in title, description, keywords
                if (query_lower in setting['title'].lower() or
                    query_lower in setting['description'].lower() or
                    any(query_lower in kw.lower() for kw in setting['keywords'])):
                    results['settings'].append({
                        'id': setting['id'],
                        'type': 'function',
                        'title': setting['title'],
                        'subtitle': 'הגדרות',
                        'description': setting['description'],
                        'metadata': {
                            'path': setting['path'],
                            'section': setting.get('section'),
                            'action': setting.get('action')
                        }
                    })
        
        # Calculate total results
        total = sum(len(results[t]) for t in results)
        
        return jsonify({
            'query': query,
            'results': results,
            'total': total
        })
        
    except Exception as e:
        log.error(f"Global search error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
