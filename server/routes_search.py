"""
Global Search API - searches across leads, calls, WhatsApp, and contacts
Supports multi-tenant with business_id filtering
"""
from flask import Blueprint, request, jsonify, session
from server.auth_api import require_api_auth
from server.db import db
from server.models_sql import Lead, Call, WhatsAppThread, User, Business
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
                    'contacts': []
                },
                'total': 0
            })
        
        # Parse types filter
        types_param = request.args.get('types', 'leads,calls,whatsapp,contacts')
        search_types = [t.strip() for t in types_param.split(',')]
        limit = request.args.get('limit', 5, type=int)
        
        results = {
            'leads': [],
            'calls': [],
            'whatsapp': [],
            'contacts': []
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
                calls_query = Call.query.filter(
                    Call.business_id == business_id,
                    or_(
                        Call.from_number.ilike(f'%{query}%'),
                        Call.to_number.ilike(f'%{query}%'),
                        Call.call_sid.ilike(f'%{query}%')
                    )
                ).order_by(Call.start_time.desc()).limit(limit)
                
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
                            'start_time': call.start_time.isoformat() if call.start_time else None,
                            'lead_id': call.lead_id
                        }
                    })
            except Exception as e:
                log.error(f"Error searching calls: {e}")
        
        # Search in WhatsApp Threads
        if 'whatsapp' in search_types:
            try:
                # Search by phone or peer name
                threads_query = WhatsAppThread.query.filter(
                    WhatsAppThread.business_id == business_id,
                    or_(
                        WhatsAppThread.phone_e164.ilike(f'%{query}%'),
                        WhatsAppThread.peer_name.ilike(f'%{query}%')
                    )
                ).order_by(WhatsAppThread.last_activity.desc()).limit(limit)
                
                for thread in threads_query.all():
                    results['whatsapp'].append({
                        'id': thread.id,
                        'type': 'whatsapp',
                        'title': f"WhatsApp - {thread.peer_name or thread.phone_e164}",
                        'subtitle': thread.phone_e164,
                        'description': f"הודעות: {thread.message_count or 0}",
                        'metadata': {
                            'phone': thread.phone_e164,
                            'peer_name': thread.peer_name,
                            'message_count': thread.message_count,
                            'unread_count': thread.unread_count or 0,
                            'last_activity': thread.last_activity.isoformat() if thread.last_activity else None,
                            'is_closed': thread.is_closed
                        }
                    })
            except Exception as e:
                log.error(f"Error searching WhatsApp threads: {e}")
        
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
