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
        # Get current user and business context - USE @require_api_auth populated g.user/g.tenant
        from flask import g
        user = getattr(g, 'user', None) or session.get('al_user') or session.get('user', {})
        tenant_id = getattr(g, 'tenant', None)
        user_role = user.get('role') if user else None
        
        # ✅ CRITICAL: Enforce business isolation for non-system_admin
        if user_role == 'system_admin':
            # System admin can optionally filter by business_id, or search all
            business_id = request.args.get('business_id', type=int) or tenant_id
            # If system_admin and no specific business - search all (business_id = None is OK)
        else:
            # ✅ Regular users MUST be filtered to their business only
            business_id = tenant_id or session.get('impersonated_tenant_id') or user.get('business_id')
            
            if not business_id:
                log.error(f"No business_id for user {user.get('email')} role {user_role}")
                return jsonify({'error': 'Business context required'}), 401
        
        # Get search parameters
        query = request.args.get('q', '').strip()
        
        log.info(f"Global search: user={user.get('email')}, role={user_role}, business_id={business_id}, query='{query}'")
        if len(query) < 2:
            log.info(f"Search query too short: '{query}'")
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
                # ✅ CRITICAL: Always filter by tenant_id (not business_id) for Leads
                leads_query = Lead.query
                
                # Apply business filter - Lead uses tenant_id field
                if business_id:
                    leads_query = leads_query.filter(Lead.tenant_id == business_id)
                elif user_role != 'system_admin':
                    # Non-admin without business_id - should not happen, but safety check
                    log.error("Non-admin user attempting search without business_id")
                    return jsonify({'error': 'Business context required'}), 401
                
                # Search by first_name, last_name, phone_e164, email, or notes
                leads_query = leads_query.filter(
                    or_(
                        Lead.first_name.ilike(f'%{query}%'),
                        Lead.last_name.ilike(f'%{query}%'),
                        Lead.phone_e164.ilike(f'%{query}%'),
                        Lead.email.ilike(f'%{query}%'),
                        Lead.notes.ilike(f'%{query}%') if hasattr(Lead, 'notes') else False
                    )
                ).order_by(Lead.created_at.desc()).limit(limit)
                
                for lead in leads_query.all():
                    full_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()
                    results['leads'].append({
                        'id': lead.id,
                        'type': 'lead',
                        'title': full_name or lead.phone_e164 or 'לא ידוע',
                        'subtitle': lead.phone_e164,
                        'description': lead.email or (lead.notes[:100] + '...' if hasattr(lead, 'notes') and lead.notes else ''),
                        'metadata': {
                            'phone': lead.phone_e164,
                            'email': lead.email,
                            'status': lead.status or 'חדש',
                            'created_at': lead.created_at.isoformat() if lead.created_at else None,
                            'source': getattr(lead, 'source', None)
                        }
                    })
            except Exception as e:
                log.error(f"Error searching leads: {e}", exc_info=True)
        
        # Search in Calls
        if 'calls' in search_types:
            try:
                # ✅ CRITICAL: Always filter by business_id for non-system_admin
                calls_query = CallLog.query
                
                # Apply business filter
                if business_id:
                    calls_query = calls_query.filter(CallLog.business_id == business_id)
                elif user_role != 'system_admin':
                    log.error("Non-admin user attempting calls search without business_id")
                    return jsonify({'error': 'Business context required'}), 401
                
                # Search by phone number or call SID
                calls_query = calls_query.filter(
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
                log.error(f"Error searching calls: {e}", exc_info=True)
        
        # Search in WhatsApp Conversations
        if 'whatsapp' in search_types:
            try:
                # ✅ CRITICAL: Always filter by business_id for non-system_admin
                conversations_query = WhatsAppConversation.query
                
                # Apply business filter
                if business_id:
                    conversations_query = conversations_query.filter(WhatsAppConversation.business_id == business_id)
                elif user_role != 'system_admin':
                    log.error("Non-admin user attempting WhatsApp search without business_id")
                    return jsonify({'error': 'Business context required'}), 401
                
                # Search by phone or customer name
                conversations_query = conversations_query.filter(
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
                # ✅ CRITICAL: Always filter by business_id for non-system_admin
                users_query = User.query
                
                # Apply business filter
                if business_id:
                    users_query = users_query.filter(User.business_id == business_id)
                elif user_role != 'system_admin':
                    log.error("Non-admin user attempting users search without business_id")
                    return jsonify({'error': 'Business context required'}), 401
                
                # Search users in the same business
                users_query = users_query.filter(
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
        # ✅ COMPLETE REGISTRY: All routes from routes.tsx with feature flags and roles
        if 'pages' in search_types or types_param == 'all' or not types_param:
            SYSTEM_PAGES = [
                # Admin Pages
                {'id': 'admin-overview', 'title': 'סקירה כללית - מנהל', 'description': 'לוח בקרה מנהל מערכת', 'keywords': ['סקירה', 'דשבורד', 'admin', 'overview'], 'path': '/app/admin/overview', 'category': 'ניהול', 'roles': ['system_admin'], 'features': []},
                {'id': 'businesses', 'title': 'ניהול עסקים', 'description': 'רשימת כל העסקים במערכת', 'keywords': ['עסקים', 'businesses', 'ניהול'], 'path': '/app/admin/businesses', 'category': 'ניהול', 'roles': ['system_admin'], 'features': []},
                {'id': 'business-minutes', 'title': 'ניהול דקות שיחה', 'description': 'צפייה בדקות שיחה לפי עסק', 'keywords': ['דקות', 'minutes', 'שיחות'], 'path': '/app/admin/business-minutes', 'category': 'ניהול', 'roles': ['system_admin'], 'features': ['calls']},
                {'id': 'prompt-studio', 'title': 'סטודיו פרומפטים', 'description': 'עריכת פרומפטים AI ובדיקה', 'keywords': ['פרומפטים', 'prompts', 'ai', 'בינה מלאכותית', 'סטודיו'], 'path': '/app/admin/prompt-studio', 'category': 'AI', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['calls']},
                
                # Business Pages
                {'id': 'dashboard', 'title': 'סקירה כללית', 'description': 'לוח בקרה עסקי', 'keywords': ['סקירה', 'דשבורד', 'dashboard', 'overview'], 'path': '/app/business/overview', 'category': 'ניהול', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
                {'id': 'leads', 'title': 'לידים', 'description': 'ניהול לידים ולקוחות פוטנציאליים', 'keywords': ['לידים', 'לקוחות', 'leads', 'crm'], 'path': '/app/leads', 'category': 'CRM', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': ['crm']},
                
                # Communication - WhatsApp
                {'id': 'whatsapp', 'title': 'WhatsApp', 'description': 'שיחות WhatsApp עם לקוחות', 'keywords': ['whatsapp', 'ווצאפ', 'וואטסאפ', 'צ\'ט'], 'path': '/app/whatsapp', 'category': 'תקשורת', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': ['whatsapp']},
                {'id': 'whatsapp-broadcast', 'title': 'תפוצת WhatsApp', 'description': 'שליחת הודעות המוניות', 'keywords': ['תפוצה', 'broadcast', 'whatsapp', 'המוני'], 'path': '/app/whatsapp-broadcast', 'category': 'תקשורת', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['whatsapp']},
                
                # Communication - Calls
                {'id': 'calls-inbound', 'title': 'שיחות נכנסות', 'description': 'שיחות טלפון נכנסות', 'keywords': ['שיחות', 'נכנס', 'inbound', 'calls', 'טלפון'], 'path': '/app/calls', 'category': 'תקשורת', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': ['calls']},
                {'id': 'calls-outbound', 'title': 'שיחות יוצאות', 'description': 'שיחות טלפון יוצאות', 'keywords': ['שיחות', 'יוצא', 'outbound', 'calls', 'טלפון'], 'path': '/app/outbound-calls', 'category': 'תקשורת', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': ['calls']},
                
                # CRM & Tasks
                {'id': 'crm', 'title': 'משימות', 'description': 'ניהול משימות ועבודות', 'keywords': ['משימות', 'tasks', 'crm', 'פרויקטים'], 'path': '/app/crm', 'category': 'CRM', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': ['crm']},
                
                # Email & Communication
                {'id': 'emails', 'title': 'מיילים', 'description': 'ניהול מיילים ותבניות', 'keywords': ['מיילים', 'emails', 'דואר', 'אימייל'], 'path': '/app/emails', 'category': 'תקשורת', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
                
                # Statistics & Reports
                {'id': 'statistics', 'title': 'סטטיסטיקות', 'description': 'דוחות וניתוח נתונים', 'keywords': ['סטטיסטיקות', 'statistics', 'דוחות', 'ניתוח'], 'path': '/app/statistics', 'category': 'דוחות', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
                
                # Financial
                {'id': 'contracts', 'title': 'חוזים', 'description': 'ניהול חוזים וחתימות דיגיטליות', 'keywords': ['חוזים', 'contracts', 'חתימה', 'signature'], 'path': '/app/contracts', 'category': 'כספים', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': ['contracts']},
                {'id': 'receipts', 'title': 'קבלות', 'description': 'ניהול קבלות והוצאות', 'keywords': ['קבלות', 'receipts', 'הוצאות', 'חשבוניות'], 'path': '/app/receipts', 'category': 'כספים', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['receipts']},
                
                # Assets & Library
                {'id': 'assets', 'title': 'מאגר', 'description': 'מאגר קבצים ומסמכים', 'keywords': ['מאגר', 'assets', 'קבצים', 'library'], 'path': '/app/assets', 'category': 'ניהול', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
                
                # Calendar
                {'id': 'calendar', 'title': 'לוח שנה', 'description': 'ניהול פגישות ותורים', 'keywords': ['לוח שנה', 'calendar', 'פגישות', 'תורים'], 'path': '/app/calendar', 'category': 'ניהול', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
                
                # Settings & Users
                {'id': 'users', 'title': 'ניהול משתמשים', 'description': 'ניהול משתמשים והרשאות', 'keywords': ['משתמשים', 'users', 'הרשאות', 'permissions'], 'path': '/app/users', 'category': 'הגדרות', 'roles': ['system_admin', 'owner', 'admin'], 'features': []},
                {'id': 'settings', 'title': 'הגדרות מערכת', 'description': 'הגדרות כלליות ואינטגרציות', 'keywords': ['הגדרות', 'settings', 'קונפיגורציה'], 'path': '/app/settings', 'category': 'הגדרות', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
            ]
            
            # Get business features (simplified - full implementation would query DB)
            # For now, we'll assume all features are enabled unless we have specific business data
            business_features = {
                'calls': True,
                'whatsapp': True,
                'crm': True,
                'contracts': True,
                'receipts': True
            }
            
            query_lower = query.lower()
            for page in SYSTEM_PAGES:
                # Check role access
                if 'roles' in page and user_role not in page.get('roles', []):
                    continue
                
                # Check feature access (filter by business features)
                if 'features' in page and page['features']:
                    # If page requires features, check if business has them
                    has_required_features = all(business_features.get(feature, False) for feature in page['features'])
                    if not has_required_features:
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
        
        # Search in Settings & Tabs (הגדרות וטאבים)
        # ✅ COMPLETE REGISTRY: All settings pages and tabs with feature flags
        if 'settings' in search_types or types_param == 'all' or not types_param:
            SYSTEM_SETTINGS = [
                # Settings Page Tabs
                {'id': 'settings-business', 'title': 'הגדרות עסק', 'description': 'פרטי העסק, שעות פעילות, אזור זמן', 'keywords': ['הגדרות', 'עסק', 'business', 'settings'], 'path': '/app/settings?tab=business', 'section': 'business', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
                {'id': 'settings-integrations', 'title': 'אינטגרציות', 'description': 'Twilio, WhatsApp, Webhook', 'keywords': ['אינטגרציות', 'integrations', 'webhook', 'twilio'], 'path': '/app/settings?tab=integrations', 'section': 'integrations', 'roles': ['system_admin', 'owner', 'admin'], 'features': []},
                {'id': 'settings-security', 'title': 'אבטחה', 'description': 'סיסמאות והרשאות', 'keywords': ['אבטחה', 'security', 'סיסמה', 'password'], 'path': '/app/settings?tab=security', 'section': 'security', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
                {'id': 'settings-notifications', 'title': 'התראות', 'description': 'הגדרות התראות ועדכונים', 'keywords': ['התראות', 'notifications', 'push'], 'path': '/app/settings?tab=notifications', 'section': 'notifications', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
                
                # Prompt Studio Tabs
                {'id': 'prompt-studio-prompts', 'title': 'עריכת פרומפטים', 'description': 'עריכת פרומפטים לשיחות ו-WhatsApp', 'keywords': ['פרומפטים', 'prompts', 'ai', 'עריכה'], 'path': '/app/admin/prompt-studio?tab=prompts', 'section': 'prompts', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['calls']},
                {'id': 'prompt-studio-builder', 'title': 'מחולל פרומפטים', 'description': 'יצירת פרומפטים חכמים באופן אוטומטי', 'keywords': ['מחולל', 'builder', 'generator', 'פרומפטים'], 'path': '/app/admin/prompt-studio?tab=builder', 'section': 'builder', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['calls']},
                {'id': 'prompt-studio-tester', 'title': 'בדיקת שיחה חיה', 'description': 'בדיקת פרומפטים בשיחה חיה', 'keywords': ['בדיקה', 'tester', 'live', 'שיחה'], 'path': '/app/admin/prompt-studio?tab=tester', 'section': 'tester', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['calls']},
                {'id': 'prompt-studio-appointments', 'title': 'הגדרות תורים', 'description': 'הגדרות קביעת פגישות ותורים', 'keywords': ['תורים', 'appointments', 'פגישות'], 'path': '/app/admin/prompt-studio?tab=appointments', 'section': 'appointments', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['calls']},
                
                # WhatsApp Broadcast Tabs
                {'id': 'whatsapp-broadcast-send', 'title': 'שליחת תפוצה', 'description': 'שליחת הודעת תפוצה ב-WhatsApp', 'keywords': ['תפוצה', 'broadcast', 'שליחה', 'send'], 'path': '/app/whatsapp-broadcast?tab=send', 'section': 'send', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['whatsapp']},
                {'id': 'whatsapp-broadcast-history', 'title': 'היסטוריית תפוצות', 'description': 'צפייה בתפוצות קודמות', 'keywords': ['היסטוריה', 'history', 'תפוצות'], 'path': '/app/whatsapp-broadcast?tab=history', 'section': 'history', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['whatsapp']},
                {'id': 'whatsapp-broadcast-templates', 'title': 'תבניות תפוצה', 'description': 'ניהול תבניות הודעות', 'keywords': ['תבניות', 'templates', 'תפוצה'], 'path': '/app/whatsapp-broadcast?tab=templates', 'section': 'templates', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['whatsapp']},
                
                # Email Page Tabs
                {'id': 'emails-all', 'title': 'כל המיילים', 'description': 'צפייה בכל המיילים', 'keywords': ['מיילים', 'emails', 'כל'], 'path': '/app/emails?tab=all', 'section': 'all', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
                {'id': 'emails-sent', 'title': 'מיילים שנשלחו', 'description': 'מיילים יוצאים', 'keywords': ['מיילים', 'נשלחו', 'sent'], 'path': '/app/emails?tab=sent', 'section': 'sent', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
                {'id': 'emails-leads', 'title': 'מיילים לפי ליד', 'description': 'מיילים מקושרים ללידים', 'keywords': ['מיילים', 'לידים', 'leads'], 'path': '/app/emails?tab=leads', 'section': 'leads', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': []},
                {'id': 'emails-templates', 'title': 'תבניות מייל', 'description': 'ניהול תבניות', 'keywords': ['תבניות', 'templates', 'מייל'], 'path': '/app/emails?tab=templates', 'section': 'templates', 'roles': ['system_admin', 'owner', 'admin'], 'features': []},
                {'id': 'emails-settings', 'title': 'הגדרות מייל', 'description': 'הגדרות Gmail וסנכרון', 'keywords': ['הגדרות', 'settings', 'gmail'], 'path': '/app/emails?tab=settings', 'section': 'settings', 'roles': ['system_admin', 'owner', 'admin'], 'features': []},
                
                # Contracts Page Tabs  
                {'id': 'contracts-list', 'title': 'חוזים', 'description': 'רשימת כל החוזים', 'keywords': ['חוזים', 'contracts', 'רשימה'], 'path': '/app/contracts?tab=list', 'section': 'list', 'roles': ['system_admin', 'owner', 'admin', 'agent'], 'features': ['contracts']},
                {'id': 'contracts-templates', 'title': 'תבניות חוזים', 'description': 'ניהול תבניות חוזים', 'keywords': ['תבניות', 'templates', 'חוזים'], 'path': '/app/contracts?tab=templates', 'section': 'templates', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['contracts']},
                
                # Admin Support Tabs
                {'id': 'admin-support-prompt', 'title': 'תמיכת פרומפטים', 'description': 'תמיכה בפרומפטים', 'keywords': ['תמיכה', 'support', 'פרומפטים'], 'path': '/app/admin/support?tab=prompt', 'section': 'prompt', 'roles': ['system_admin'], 'features': []},
                {'id': 'admin-support-phones', 'title': 'ניהול מספרי טלפון', 'description': 'ניהול מספרי טלפון Twilio', 'keywords': ['טלפון', 'phones', 'twilio'], 'path': '/app/admin/support?tab=phones', 'section': 'phones', 'roles': ['system_admin'], 'features': ['calls']},
                
                # Business Details Tabs (Admin)
                {'id': 'business-details-overview', 'title': 'פרטי עסק', 'description': 'סקירת פרטי העסק', 'keywords': ['עסק', 'business', 'פרטים'], 'path': '/app/admin/businesses/:id?tab=overview', 'section': 'overview', 'roles': ['system_admin'], 'features': []},
                {'id': 'business-details-users', 'title': 'משתמשי עסק', 'description': 'משתמשים של העסק', 'keywords': ['משתמשים', 'users', 'עסק'], 'path': '/app/admin/businesses/:id?tab=users', 'section': 'users', 'roles': ['system_admin'], 'features': []},
                {'id': 'business-details-integrations', 'title': 'אינטגרציות עסק', 'description': 'אינטגרציות של העסק', 'keywords': ['אינטגרציות', 'integrations'], 'path': '/app/admin/businesses/:id?tab=integrations', 'section': 'integrations', 'roles': ['system_admin'], 'features': []},
                {'id': 'business-details-audit', 'title': 'לוג ביקורת', 'description': 'רישום פעילות העסק', 'keywords': ['ביקורת', 'audit', 'לוג'], 'path': '/app/admin/businesses/:id?tab=audit', 'section': 'audit', 'roles': ['system_admin'], 'features': []},
                
                # Legacy / Backwards Compatibility
                {'id': 'webhook', 'title': 'Webhook', 'description': 'הגדרות Webhook ל-Twilio', 'keywords': ['webhook', 'twilio', 'אינטגרציות'], 'path': '/app/settings?tab=integrations', 'section': 'integrations', 'roles': ['system_admin', 'owner', 'admin'], 'features': []},
                {'id': 'ai-prompts', 'title': 'AI Prompts', 'description': 'עריכת פרומפטים', 'keywords': ['ai', 'prompts', 'פרומפטים'], 'path': '/app/admin/prompt-studio', 'section': 'ai', 'roles': ['system_admin', 'owner', 'admin'], 'features': ['calls']},
            ]
            
            # Get business features for filtering
            business_features = {
                'calls': True,
                'whatsapp': True,
                'crm': True,
                'contracts': True,
                'receipts': True
            }
            
            query_lower = query.lower()
            for setting in SYSTEM_SETTINGS:
                # Check role access
                if 'roles' in setting and user_role not in setting.get('roles', []):
                    continue
                
                # Check feature access (filter by business features)
                if 'features' in setting and setting['features']:
                    has_required_features = all(business_features.get(feature, False) for feature in setting['features'])
                    if not has_required_features:
                        continue
                
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
        
        log.info(f"Search results for '{query}': {total} total (leads:{len(results['leads'])}, calls:{len(results['calls'])}, whatsapp:{len(results['whatsapp'])}, contacts:{len(results['contacts'])}, pages:{len(results['pages'])}, settings:{len(results['settings'])})")
        
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
