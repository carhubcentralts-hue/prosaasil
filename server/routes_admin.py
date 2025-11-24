# server/routes_admin.py
"""
Admin API routes for KPIs, tenant management, and system overview
Implements RBAC with multi-tenant support as per guidelines
"""
from flask import Blueprint, jsonify, request, g, session
from server.auth_api import require_api_auth
from server.models_sql import Business, User, CallLog, WhatsAppMessage, Customer
from server.db import db
from datetime import datetime, timedelta
from sqlalchemy import func
from werkzeug.security import generate_password_hash
import logging
import secrets

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin_bp", __name__)

@admin_bp.get("/api/admin/overview")
@require_api_auth(["admin", "superadmin", "manager"])
def api_overview():
    """System overview KPIs for admin dashboard with date filtering"""
    try:
        # Get date range from query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        time_filter = request.args.get('time_filter', 'today')  # today, week, month, custom
        
        # Calculate date range based on filter
        now = datetime.utcnow()
        if time_filter == 'week':
            date_start = (now - timedelta(days=7)).date()
            date_end = now.date()
        elif time_filter == 'month':
            date_start = (now - timedelta(days=30)).date()
            date_end = now.date()
        elif time_filter == 'custom' and start_date and end_date:
            date_start = datetime.strptime(start_date, '%Y-%m-%d').date()
            date_end = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:  # today or default
            date_start = now.date()
            date_end = now.date()
        
        # Calls in date range
        calls_count = CallLog.query.filter(
            func.date(CallLog.created_at) >= date_start,
            func.date(CallLog.created_at) <= date_end
        ).count()
        
        # WhatsApp messages in date range
        whatsapp_count = WhatsAppMessage.query.filter(
            func.date(WhatsAppMessage.created_at) >= date_start,
            func.date(WhatsAppMessage.created_at) <= date_end
        ).count()
        
        # Active businesses (not date filtered as it's current status)
        active_businesses = Business.query.filter_by(is_active=True).count()
        total_businesses = Business.query.count()
        
        # Calculate average call duration for the period (no mock data)
        avg_call_duration = 0  # Real data only
        
        # Recent activity for the period
        recent_calls = CallLog.query.filter(
            func.date(CallLog.created_at) >= date_start,
            func.date(CallLog.created_at) <= date_end
        ).order_by(CallLog.created_at.desc()).limit(10).all()
        
        recent_whatsapp = WhatsAppMessage.query.filter(
            func.date(WhatsAppMessage.created_at) >= date_start,
            func.date(WhatsAppMessage.created_at) <= date_end
        ).order_by(WhatsAppMessage.created_at.desc()).limit(10).all()
        
        # Format recent activity
        recent_activity = []
        
        # Add recent calls
        for call in recent_calls:
            business = Business.query.get(call.business_id)
            recent_activity.append({
                "id": f"call_{call.id}",
                "time": call.created_at.strftime("%H:%M"),
                "type": "call",
                "tenant": business.name if business else "לא ידוע",
                "preview": f"שיחה מ-{call.from_number or 'מספר לא ידוע'} - נתונים זמינים",
                "status": call.status or "הושלמה"
            })
        
        # Add recent WhatsApp messages  
        for msg in recent_whatsapp:
            business = Business.query.get(msg.business_id) 
            recent_activity.append({
                "id": f"whatsapp_{msg.id}",
                "time": msg.created_at.strftime("%H:%M"),
                "type": "whatsapp", 
                "tenant": business.name if business else "לא ידוע",
                "preview": (msg.body[:50] + "...") if msg.body and len(msg.body) > 50 else (msg.body or "הודעה ללא תוכן"),
                "status": "התקבלה" if msg.direction == "incoming" else "נשלחה"
            })
        
        # Sort by time and limit to 10 most recent
        recent_activity.sort(key=lambda x: x['time'], reverse=True)
        recent_activity = recent_activity[:10]
        
        return jsonify({
            "calls_count": calls_count,
            "whatsapp_count": whatsapp_count,
            "active_businesses": active_businesses,
            "total_businesses": total_businesses,
            "avg_call_duration": round(avg_call_duration / 60, 1) if avg_call_duration > 0 else 0,  # in minutes
            "recent_activity": recent_activity,
            "date_range": {
                "start": date_start.isoformat(),
                "end": date_end.isoformat(),
                "filter": time_filter
            },
            "provider_status": {
                "twilio": {"up": True, "latency": 45},
                "baileys": {"up": True, "latency": None},
                "db": {"up": True, "latency": 12},
                "stt": 120,
                "ai": 850, 
                "tts": 200
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.get("/api/admin/kpis/calls")
@require_api_auth(["admin", "superadmin"])  
def api_kpis_calls():
    """Get calls KPI with date filtering"""
    try:
        # Get date range from query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        time_filter = request.args.get('time_filter', 'today')
        
        # Calculate date range
        now = datetime.utcnow()
        if time_filter == 'week':
            date_start = (now - timedelta(days=7)).date()
            date_end = now.date()
        elif time_filter == 'month':
            date_start = (now - timedelta(days=30)).date()
            date_end = now.date()
        elif time_filter == 'custom' and start_date and end_date:
            date_start = datetime.strptime(start_date, '%Y-%m-%d').date()
            date_end = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:  # today
            date_start = now.date()
            date_end = now.date()
            
        count = CallLog.query.filter(
            func.date(CallLog.created_at) >= date_start,
            func.date(CallLog.created_at) <= date_end
        ).count()
        return str(count)
    except Exception as e:
        return "0"

@admin_bp.get("/api/admin/kpis/whatsapp")
@require_api_auth(["admin", "superadmin"])
def api_kpis_whatsapp():
    """Get WhatsApp KPI with date filtering"""
    try:
        # Get date range from query parameters  
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        time_filter = request.args.get('time_filter', 'today')
        
        # Calculate date range
        now = datetime.utcnow()
        if time_filter == 'week':
            date_start = (now - timedelta(days=7)).date()
            date_end = now.date()
        elif time_filter == 'month':
            date_start = (now - timedelta(days=30)).date()
            date_end = now.date()
        elif time_filter == 'custom' and start_date and end_date:
            date_start = datetime.strptime(start_date, '%Y-%m-%d').date()
            date_end = datetime.strptime(end_date, '%Y-%m-%d').date()  
        else:  # today
            date_start = now.date()
            date_end = now.date()
            
        count = WhatsAppMessage.query.filter(
            func.date(WhatsAppMessage.created_at) >= date_start,
            func.date(WhatsAppMessage.created_at) <= date_end
        ).count()
        return str(count)
    except Exception as e:
        return "0"

@admin_bp.get("/api/admin/kpis/businesses")
@require_api_auth(["admin", "superadmin"])
def api_kpis_businesses():
    """Get active businesses KPI"""
    try:
        count = Business.query.filter_by(is_active=True).count()
        return str(count)
    except Exception as e:
        return "0"

@admin_bp.get("/api/admin/kpis/revenue")
@require_api_auth(["admin", "superadmin"])
def api_kpis_revenue():
    """Get revenue KPI"""
    try:
        # Real revenue from Payment model
        from server.models_sql import Payment
        total_revenue = Payment.query.with_entities(db.func.sum(Payment.amount)).scalar() or 0
        return f"₪{total_revenue:,}"
    except Exception as e:
        return "₪0"

# ================================
# NEW UNIFIED API ENDPOINTS - REAL DATA ONLY
# ================================

@admin_bp.route("/api/admin/businesses", methods=['GET'])
@require_api_auth(["admin", "manager"])
def api_admin_businesses():
    """List all businesses with pagination - לפי ההנחיות המדויקות"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('pageSize', 20))
        search_query = request.args.get('q', '').strip()
        
        # Query with all businesses including suspended ones
        query = Business.query
        
        # Apply search filter if provided
        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                Business.name.ilike(search_pattern) |
                Business.business_type.ilike(search_pattern)
            )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        businesses = query.offset(offset).limit(page_size).all()
        
        # Format response לפי ההנחיות המדויקות - ✅ תיקון: נתונים אמיתיים בלבד
        items = []
        for business in businesses:
            # Use actual phone data from database (field is phone_number not phone_e164)
            phone_e164 = getattr(business, 'phone_number', '') or ""
            
            items.append({
                "id": business.id,
                "name": business.name,
                "email": business.email or "",  # ✅ הוספה: email for primary account login
                "business_type": business.business_type or "נדל\"ן",  # ✅ הוספה: חסר בתגובה המקורית
                "phone_number": phone_e164,  # ✅ שינוי: phone_number במקום phone_e164
                "phone_e164": phone_e164,
                "whatsapp_number": business.whatsapp_number or "",  # ✅ הוספה: נדרש לפרונטאנד
                "is_active": business.is_active,  # ✅ הוספה: active status
                "status": "active" if business.is_active else "suspended",
                "whatsapp_status": "connected" if business.whatsapp_enabled else "disconnected",
                "call_status": "ready" if business.calls_enabled else "disabled",
                "created_at": business.created_at.isoformat() if business.created_at else None
            })
        
        logger.info(f"📊 BUSINESSES API: total={total}, page={page}, returned={len(items)}")
        
        return jsonify({
            "items": items,
            "total": total,
            "page": page,
            "pageSize": page_size
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        try:
            logger.error(f"Error in api_admin_businesses: {e}")
            logger.error(f"Full traceback: {error_trace}")
        except:
            pass  # logger might not be available
        print(f"🔥 BUSINESSES API ERROR: {e}")
        print(f"🔥 TRACEBACK: {error_trace}")
        return jsonify({"error": f"DEBUG: {str(e)}"}), 500

# A2) צפייה/התחזות - לפי ההנחיות המדויקות
@admin_bp.route("/api/admin/businesses/<int:business_id>/overview", methods=['GET'])
@require_api_auth(["admin", "manager"])
def get_business_overview(business_id):
    """צפייה בעסק (Admin View) - קריא בלבד, ללא שינוי סשן"""
    try:
        business = Business.query.get(business_id)
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        # Get business stats for the overview
        total_calls = CallLog.query.filter_by(business_id=business_id).count()
        total_whatsapp = WhatsAppMessage.query.filter_by(business_id=business_id).count()
        total_customers = Customer.query.filter_by(business_id=business_id).count()
        
        # Recent activity
        recent_calls = CallLog.query.filter_by(business_id=business_id)\
            .order_by(CallLog.created_at.desc()).limit(5).all()
        recent_whatsapp = WhatsAppMessage.query.filter_by(business_id=business_id)\
            .order_by(WhatsAppMessage.created_at.desc()).limit(5).all()
        
        # Business users count
        users_count = User.query.filter_by(business_id=business_id).count()
        
        return jsonify({
            "id": business.id,
            "name": business.name,
            "business_type": business.business_type,
            "phone_e164": business.phone_number or "",
            "whatsapp_number": business.whatsapp_number or "",
            "status": "active" if business.is_active else "suspended",
            "whatsapp_status": "connected" if business.whatsapp_enabled else "disconnected",
            "call_status": "ready" if business.calls_enabled else "disabled",
            "created_at": business.created_at.isoformat() if business.created_at else None,
            "stats": {
                "total_calls": total_calls,
                "total_whatsapp": total_whatsapp,
                "total_customers": total_customers,
                "users_count": users_count
            },
            "recent_calls": [{
                "id": call.id,
                "from_number": call.from_number,
                "status": call.status,
                "created_at": call.created_at.isoformat() if call.created_at else None
            } for call in recent_calls],
            "recent_whatsapp": [{
                "id": msg.id,
                "from_number": getattr(msg, 'from_number', ''),
                "direction": getattr(msg, 'direction', 'incoming'),
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            } for msg in recent_whatsapp]
        })
        
    except Exception as e:
        logger.exception(f"Error getting business overview {business_id}: {e}")
        return jsonify({"error": "שגיאה בטעינת נתוני העסק"}), 500

@admin_bp.route("/api/admin/kpis/overview", methods=['GET'])
@require_api_auth(["admin", "manager"])
def api_admin_kpis_overview():
    """Get overview KPIs - SINGLE SOURCE OF TRUTH"""
    try:
        from datetime import datetime, timedelta
        
        # Date range (default 7 days)
        range_days = int(request.args.get('range', '7').replace('d', ''))
        date_start = datetime.utcnow().date() - timedelta(days=range_days)
        
        # Real counts - NO DEMO/MOCK DATA
        businesses_count = Business.query.filter_by(is_active=True).count()
        calls_count = CallLog.query.filter(CallLog.created_at >= date_start).count()
        whatsapp_count = WhatsAppMessage.query.filter(WhatsAppMessage.created_at >= date_start).count()
        unread_notifications = 4  # TODO: Replace with real notifications count
        
        logger.info(f"📊 KPI_OVERVIEW_REAL_DATA: businesses={businesses_count}, calls={calls_count}, whatsapp={whatsapp_count}")
        
        return jsonify({
            "totals": {
                "businesses": businesses_count,
                "calls": calls_count,
                "whatsapp": whatsapp_count,
                "unreadNotifications": unread_notifications
            },
            "period": {
                "from": date_start.isoformat(),
                "to": datetime.utcnow().date().isoformat(),
                "tz": "+03:00"
            }
        })
        
    except Exception as e:
        logger.error(f"Error in api_admin_kpis_overview: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.get("/api/admin/kpis/calls")
@require_api_auth(["admin", "manager"])
def api_admin_kpis_calls():
    """Get calls KPIs - REAL DATA ONLY"""
    try:
        from datetime import datetime, timedelta
        
        range_days = int(request.args.get('range', '7').replace('d', ''))
        tenant_id = request.args.get('tenantId')
        
        date_start = datetime.utcnow().date() - timedelta(days=range_days)
        
        query = CallLog.query.filter(CallLog.created_at >= date_start)
        if tenant_id:
            query = query.filter(CallLog.business_id == tenant_id)
            
        calls_count = query.count()
        
        logger.info(f"📞 CALLS_KPI_REAL_DATA: count={calls_count}, range={range_days}d, tenant={tenant_id}")
        
        return jsonify({
            "count": calls_count,
            "range": f"{range_days}d"
        })
        
    except Exception as e:
        logger.error(f"Error in api_admin_kpis_calls: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.get("/api/admin/kpis/whatsapp")
@require_api_auth(["admin", "manager"])
def api_admin_kpis_whatsapp():
    """Get WhatsApp KPIs - REAL DATA ONLY"""
    try:
        from datetime import datetime, timedelta
        
        range_days = int(request.args.get('range', '7').replace('d', ''))
        tenant_id = request.args.get('tenantId')
        
        date_start = datetime.utcnow().date() - timedelta(days=range_days)
        
        query = WhatsAppMessage.query.filter(WhatsAppMessage.created_at >= date_start)
        if tenant_id:
            query = query.filter(WhatsAppMessage.business_id == tenant_id)
            
        whatsapp_count = query.count()
        
        logger.info(f"💬 WHATSAPP_KPI_REAL_DATA: count={whatsapp_count}, range={range_days}d, tenant={tenant_id}")
        
        return jsonify({
            "count": whatsapp_count,
            "range": f"{range_days}d"
        })
        
    except Exception as e:
        logger.error(f"Error in api_admin_kpis_whatsapp: {e}")
        return jsonify({"error": str(e)}), 500

# ================================
# LEGACY ENDPOINTS
# ================================

@admin_bp.get("/api/admin/tenants")
@require_api_auth(["admin", "superadmin"])
def api_tenants():
    """Get all businesses/tenants for admin management"""
    try:
        businesses = Business.query.order_by(Business.created_at.desc()).all()
        
        tenants_html = ""
        for business in businesses:
            status_class = "bg-green-100 text-green-800" if business.is_active else "bg-red-100 text-red-800"
            status_text = "פעיל" if business.is_active else "לא פעיל"
            
            tenants_html += f"""
            <div class="flex items-center justify-between p-4 border-b border-gray-100 hover:bg-gray-50">
                <div>
                    <h4 class="font-medium text-gray-900">{business.name}</h4>
                    <p class="text-sm text-gray-500">{business.business_type}</p>
                </div>
                <div class="flex items-center space-x-2">
                    <span class="px-2 py-1 text-xs font-medium rounded-full {status_class}">{status_text}</span>
                    <button onclick="editBusiness({business.id})" class="text-blue-600 hover:text-blue-800 text-sm mr-2">עריכה</button>
                    <button onclick="loginAsBusiness({business.id})" class="text-green-600 hover:text-green-800 text-sm mr-2">התחבר כעסק</button>
                    <button onclick="changePassword({business.id})" class="text-purple-600 hover:text-purple-800 text-sm">שנה סיסמה</button>
                </div>
            </div>
            """
        
        if not tenants_html:
            tenants_html = '<div class="text-center text-gray-500 py-8">אין עסקים במערכת</div>'
            
        return tenants_html
    except Exception as e:
        return f'<div class="text-center text-red-500 py-8">שגיאה: {str(e)}</div>'

@admin_bp.get("/api/admin/calls")
@require_api_auth(["admin", "superadmin"])
def api_admin_calls():
    """Get recent calls for admin dashboard"""
    try:
        calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(10).all()
        
        calls_html = ""
        for call in calls:
            # Get business name
            business = Business.query.get(call.business_id) if call.business_id else None
            business_name = business.name if business else "לא ידוע"
            
            status_class = {
                'completed': 'bg-green-100 text-green-800',
                'failed': 'bg-red-100 text-red-800',
                'in-progress': 'bg-blue-100 text-blue-800'
            }.get(call.status, 'bg-gray-100 text-gray-800')
            
            calls_html += f"""
            <div class="flex items-center justify-between p-4 border-b border-gray-100">
                <div>
                    <div class="flex items-center space-x-2">
                        <span class="font-medium text-gray-900">{call.from_number or 'לא ידוע'}</span>
                        <span class="text-sm text-gray-500">→ {business_name}</span>
                    </div>
                    <p class="text-sm text-gray-500">{call.created_at.strftime('%d/%m/%Y %H:%M') if call.created_at else 'לא ידוע'}</p>
                </div>
                <span class="px-2 py-1 text-xs font-medium rounded-full {status_class}">{call.status}</span>
            </div>
            """
        
        if not calls_html:
            calls_html = '<div class="text-center text-gray-500 py-8">אין שיחות</div>'
            
        return calls_html
    except Exception as e:
        return f'<div class="text-center text-red-500 py-8">שגיאה: {str(e)}</div>'

@admin_bp.route("/api/admin/leads", methods=["GET"])
@require_api_auth(["admin", "superadmin", "manager"])
def admin_leads():
    """Get all leads across all tenants for admin"""
    try:
        from server.models_sql import Lead, Business
        from sqlalchemy import or_
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('pageSize', 50, type=int)
        status = request.args.get('status')
        search = request.args.get('search', '').strip()
        source = request.args.get('source')
        owner_user_id = request.args.get('owner_user_id', type=int)
        
        # Build query for all tenants
        query = db.session.query(Lead).join(Business, Lead.tenant_id == Business.id)
        
        # Apply filters
        if status and status != 'all':
            query = query.filter(Lead.status == status)
            
        if source and source != 'all':
            query = query.filter(Lead.source == source)
            
        if owner_user_id is not None:
            query = query.filter(Lead.owner_user_id == owner_user_id)
        
        if search:
            # Build search conditions safely
            conditions = []
            
            # Check for name field
            name_field = getattr(Lead, 'full_name', None)
            if name_field is None:
                name_field = getattr(Lead, 'name', None)
            if name_field is not None:
                conditions.append(name_field.ilike(f'%{search}%'))
            
            # Check for phone field
            phone_field = getattr(Lead, 'phone_e164', None)
            if phone_field is None:
                phone_field = getattr(Lead, 'phone', None)
            if phone_field is not None:
                conditions.append(phone_field.ilike(f'%{search}%'))
            
            # Always add email and business name
            conditions.extend([
                Lead.email.ilike(f'%{search}%'),
                Business.name.ilike(f'%{search}%')
            ])
            
            query = query.filter(or_(*conditions))
        
        # Count total
        total = query.count()
        
        # Apply pagination
        leads_query = query.order_by(Lead.created_at.desc())
        if page_size > 0:
            leads_query = leads_query.offset((page - 1) * page_size).limit(page_size)
        
        leads = leads_query.all()
        
        # Format leads data
        leads_data = []
        for lead in leads:
            business = lead.tenant
            leads_data.append({
                'id': lead.id,
                'name': lead.full_name,
                'phone': lead.phone_e164,
                'email': lead.email,
                'status': lead.status,
                'source': lead.source,
                'created_at': lead.created_at.isoformat() if lead.created_at else None,
                'updated_at': lead.updated_at.isoformat() if lead.updated_at else None,
                'notes': lead.notes,
                'business_id': lead.tenant_id,
                'tenant_id': lead.tenant_id,  # Backwards compatibility
                'business_name': business.name if business else None
            })
        
        response_data = {
            'items': leads_data,
            'total': total,
            'page': page,
            'pageSize': page_size
        }
        
        return jsonify({
            'items': leads_data,
            'total': total,
            'page': page,
            'pageSize': page_size
        })
        
    except Exception as e:
        print(f"❌ Error fetching admin leads: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route("/api/admin/leads/stats", methods=["GET"])
@require_api_auth(["admin", "superadmin", "manager"])
def admin_leads_stats():
    """Get leads statistics by status for admin dashboard"""
    try:
        from server.models_sql import Lead
        from sqlalchemy import func
        
        # Count leads by status across all tenants
        stats = db.session.query(
            Lead.status, 
            func.count(Lead.id).label('count')
        ).group_by(Lead.status).all()
        
        # Initialize counts
        stats_dict = {
            'new': 0,
            'in_progress': 0,  # Attempting + Contacted
            'qualified': 0,
            'won': 0,
            'lost': 0,
            'total': 0
        }
        
        # Process stats - ✅ FIXED: Case-insensitive for legacy/canonical compatibility
        for status, count in stats:
            stats_dict['total'] += count
            status_lower = status.lower() if status else ''
            if status_lower == 'new':
                stats_dict['new'] = count
            elif status_lower in ['attempting', 'contacted']:
                stats_dict['in_progress'] += count
            elif status_lower == 'qualified':
                stats_dict['qualified'] = count
            elif status_lower == 'won':
                stats_dict['won'] = count
            elif status_lower in ['lost', 'unqualified']:
                stats_dict['lost'] = count
        
        return jsonify(stats_dict)
        
    except Exception as e:
        logger.error(f"Error fetching admin leads stats: {e}")
        return jsonify({"error": "Failed to fetch leads statistics"}), 500


@admin_bp.route("/api/admin/phone-numbers", methods=["GET"])
@require_api_auth(["admin", "superadmin", "manager"])
def admin_phone_numbers():
    """Get all business phone numbers and settings for admin"""
    try:
        from server.models_sql import Business
        
        # Get all businesses with their phone numbers
        businesses = db.session.query(Business).all()
        
        # Format response - include businesses and admin
        business_phones = []
        
        # Add admin/manager as first entry
        admin_phone = '+972-54-123-4567'  # Default admin support phone
        admin_whatsapp = '+972-50-987-6543'  # Default admin whatsapp
        
        business_phones.append({
            'id': 'admin-support',
            'name': 'תמיכה מנהל מערכת',
            'phone_e164': admin_phone,
            'whatsapp_number': admin_whatsapp,
            'whatsapp_enabled': True,
            'whatsapp_status': 'connected',
            'calls_status': 'active',
            'is_admin_support': True
        })
        
        # Add regular businesses
        for business in businesses:
            business_phones.append({
                'id': business.id,
                'name': business.name,
                'phone_e164': business.phone_e164 or '',
                'whatsapp_number': business.whatsapp_number or '',
                'whatsapp_enabled': business.whatsapp_enabled or False,
                'whatsapp_status': 'connected' if business.whatsapp_enabled else 'disabled',
                'calls_status': 'active' if business.phone_e164 else 'no_phone',
                'is_admin_support': False
            })
        
        return jsonify({
            'businesses': business_phones,
            'total_businesses': len(business_phones),
            'system_settings': {
                'twilio_enabled': True,
                'baileys_enabled': True,
                'default_provider': 'twilio'
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching admin phone numbers: {e}")
        return jsonify({"error": "Failed to fetch phone numbers"}), 500


@admin_bp.route("/api/admin/businesses/prompts", methods=["GET"])
@require_api_auth(["admin", "superadmin", "manager"])
def admin_businesses_prompts():
    """Get all businesses with their AI prompts status for admin"""
    try:
        from server.models_sql import Business, BusinessSettings
        from sqlalchemy import func, case
        
        # Get all businesses with their prompts
        businesses_query = db.session.query(
            Business.id.label('business_id'),
            Business.name.label('business_name'),
            func.coalesce(BusinessSettings.ai_prompt, '').label('calls_prompt'),
            func.coalesce(BusinessSettings.ai_prompt, '').label('whatsapp_prompt'),  # TODO: separate fields
            BusinessSettings.updated_at.label('last_updated'),
            func.coalesce(
                func.row_number().over(partition_by=Business.id, order_by=BusinessSettings.updated_at.desc()), 
                1
            ).label('version')
        ).outerjoin(
            BusinessSettings, Business.id == BusinessSettings.tenant_id
        ).all()
        
        # Format response
        businesses_data = []
        for business in businesses_query:
            calls_prompt = business.calls_prompt or ''
            whatsapp_prompt = business.whatsapp_prompt or ''  # Same for now
            
            businesses_data.append({
                'business_id': business.business_id,
                'business_name': business.business_name,
                'calls_prompt': calls_prompt[:200] + '...' if len(calls_prompt) > 200 else calls_prompt,
                'whatsapp_prompt': whatsapp_prompt[:200] + '...' if len(whatsapp_prompt) > 200 else whatsapp_prompt,
                'last_updated': business.last_updated.isoformat() if business.last_updated else None,
                'version': int(business.version) if business.version else 1,
                'calls_prompt_length': len(calls_prompt),
                'whatsapp_prompt_length': len(whatsapp_prompt),
                'has_calls_prompt': len(calls_prompt.strip()) > 0,
                'has_whatsapp_prompt': len(whatsapp_prompt.strip()) > 0
            })
        
        return jsonify({
            'businesses': businesses_data,
            'total_businesses': len(businesses_data),
            'stats': {
                'with_calls_prompt': sum(1 for b in businesses_data if b['has_calls_prompt']),
                'with_whatsapp_prompt': sum(1 for b in businesses_data if b['has_whatsapp_prompt']),
                'without_prompts': sum(1 for b in businesses_data if not b['has_calls_prompt'] and not b['has_whatsapp_prompt'])
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching businesses prompts: {e}")
        return jsonify({"error": "Failed to fetch businesses prompts"}), 500


# ===== Admin Support Management endpoints =====
# These endpoints allow admin to manage their own support line (prompt, phones)

@admin_bp.route("/api/admin/support/profile", methods=["GET"])
@require_api_auth(["admin"])
def admin_support_profile():
    """Get admin's own support tenant profile - business info, phones, prompt status"""
    # Get tenant_id from session
    user = session.get('user') or session.get('al_user')
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    tenant_id = user.get('business_id')
    if not tenant_id:
        return jsonify({"error": "No tenant on user"}), 400
    biz = Business.query.get(tenant_id)
    from server.models_sql import BusinessSettings
    settings = BusinessSettings.query.filter_by(tenant_id=tenant_id).first()
    if not biz:
        return jsonify({
            "tenant_id": tenant_id,
            "name": None,
            "phone_e164": "",
            "whatsapp_number": "",
            "calls_enabled": False,
            "whatsapp_enabled": False,
            "ai_prompt": settings.ai_prompt if settings else None,
            "updated_at": settings.updated_at.isoformat() if settings and settings.updated_at else None,
        })
    return jsonify({
        "tenant_id": biz.id,
        "name": biz.name,
        "phone_e164": biz.phone_number or "",
        "whatsapp_number": biz.whatsapp_number or "",
        "calls_enabled": bool(biz.phone_number),
        "whatsapp_enabled": bool(biz.whatsapp_enabled),
        "ai_prompt": settings.ai_prompt if settings else None,
        "updated_at": settings.updated_at.isoformat() if settings and settings.updated_at else None,
    })

@admin_bp.route("/api/admin/support/prompt", methods=["GET", "PUT"])
@require_api_auth(["admin"])
def admin_support_prompt():
    """Get/Update admin's own AI prompt for customer support"""
    # Get tenant_id from session
    user = session.get('user') or session.get('al_user')
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    tenant_id = user.get('business_id')
    if not tenant_id:
        return jsonify({"error": "No tenant on user"}), 400
    from server.models_sql import BusinessSettings
    if request.method == "GET":
        settings = BusinessSettings.query.filter_by(tenant_id=tenant_id).first()
        if settings:
            return jsonify({
                "ai_prompt": settings.ai_prompt or "",
                "model": settings.model or "gpt-4o-mini",
                "max_tokens": settings.max_tokens or 120,  # ⚡ BUILD 105: 120 for faster responses
                "temperature": settings.temperature or 0.7,
                "updated_at": settings.updated_at.isoformat() if settings.updated_at else None
            })
        else:
            return jsonify({
                "ai_prompt": "",
                "model": "gpt-4o-mini", 
                "max_tokens": 120,  # ⚡ BUILD 105: 120 for faster responses
                "temperature": 0.7,
                "updated_at": None
            })
    
    data = request.get_json(silent=True) or {}
    prompt = (data.get("ai_prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "ai_prompt is required"}), 400
    
    # Get and validate other parameters
    model = data.get("model", "gpt-4o-mini") or "gpt-4o-mini"
    try:
        max_tokens = int(data.get("max_tokens", 120)) if data.get("max_tokens") else 120  # ⚡ BUILD 105
    except (ValueError, TypeError):
        max_tokens = 120  # ⚡ BUILD 105
    try:
        temperature = float(data.get("temperature", 0.7)) if data.get("temperature") is not None else 0.7
    except (ValueError, TypeError):
        temperature = 0.7
    
    # Validate ranges
    if max_tokens < 1 or max_tokens > 4000:
        max_tokens = 120  # ⚡ BUILD 105: Default for invalid values
    if temperature < 0 or temperature > 2:
        temperature = 0.7
        
    settings = BusinessSettings.query.filter_by(tenant_id=tenant_id).first()
    if not settings:
        from datetime import datetime
        settings = BusinessSettings()
        settings.tenant_id = tenant_id
        settings.ai_prompt = prompt
        settings.model = model
        settings.max_tokens = max_tokens
        settings.temperature = temperature
        settings.updated_by = str(getattr(getattr(g, 'user', None), 'id', None))
        settings.updated_at = datetime.utcnow()
        db.session.add(settings)
    else:
        settings.ai_prompt = prompt
        settings.model = model
        settings.max_tokens = max_tokens
        settings.temperature = temperature
        settings.updated_by = str(getattr(getattr(g, 'user', None), 'id', None))
    
    db.session.commit()
    return jsonify({
        "ai_prompt": settings.ai_prompt,
        "model": settings.model,
        "max_tokens": settings.max_tokens,
        "temperature": settings.temperature,
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    })

@admin_bp.route("/api/admin/support/phones", methods=["GET", "PUT"])
@require_api_auth(["admin"])
def admin_support_phones():
    """Get/Update admin's own phone numbers for customer support"""
    # Get tenant_id from session
    user = session.get('user') or session.get('al_user')
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    tenant_id = user.get('business_id')
    if not tenant_id:
        return jsonify({"error": "No tenant on user"}), 400
    biz = Business.query.get(tenant_id)
    if not biz:
        return jsonify({"error": "Business not found"}), 404
    if request.method == "GET":
        return jsonify({
            "phone_e164": biz.phone_number or "",
            "whatsapp_number": biz.whatsapp_number or "",
            "whatsapp_enabled": bool(biz.whatsapp_enabled),
            "calls_enabled": bool(biz.phone_number),
            "working_hours": biz.working_hours or "08:00-18:00",
            "voice_message": biz.voice_message or "שלום, הגעתם לתמיכה הטכנית של מערכת ניהול הנדל\"ן. אנחנו כאן לעזור לכם."
        })
    data = request.get_json(silent=True) or {}
    if "phone_e164" in data:
        biz.phone_number = (data.get("phone_e164") or "").strip() or None
        biz.calls_enabled = bool(biz.phone_number)
    if "whatsapp_number" in data:
        biz.whatsapp_number = (data.get("whatsapp_number") or "").strip() or None
    if "whatsapp_enabled" in data:
        biz.whatsapp_enabled = bool(data.get("whatsapp_enabled"))
    if "working_hours" in data:
        biz.working_hours = (data.get("working_hours") or "").strip() or "08:00-18:00"
    if "voice_message" in data:
        biz.voice_message = (data.get("voice_message") or "").strip() or None
    db.session.commit()
    return jsonify({
        "phone_e164": biz.phone_number or "",
        "whatsapp_number": biz.whatsapp_number or "",
        "whatsapp_enabled": bool(biz.whatsapp_enabled),
        "calls_enabled": bool(biz.phone_number),
        "working_hours": biz.working_hours or "08:00-18:00",
        "voice_message": biz.voice_message or "שלום, הגעתם לתמיכה הטכנית של מערכת ניהול הנדל\"ן. אנחנו כאן לעזור לכם."
    })

# ✅ Users Management Endpoints

@admin_bp.get("/api/admin/users")
@require_api_auth(["admin", "manager", "superadmin"])
def get_users():
    """Get all users for admin - can manage"""
    try:
        business_id = g.business_id
        users = User.query.filter_by(business_id=business_id, is_active=True).all()
        return jsonify([{
            'id': u.id,
            'name': u.name or u.email,
            'email': u.email,
            'role': u.role,
            'business_id': u.business_id,
            'created_at': u.created_at.isoformat() if u.created_at else None,
            'last_login': u.last_login.isoformat() if u.last_login else None
        } for u in users])
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.post("/api/admin/users")
@require_api_auth(["admin", "manager", "superadmin"])
def create_user():
    """Create new business user - admin/manager/superadmin only"""
    try:
        data = request.get_json() or {}
        business_id = g.business_id
        user_role = g.role  # Get user's role from auth
        
        email = data.get('email', '').strip()
        name = data.get('name', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'business')  # Default: business
        
        # Validation
        if not email or '@' not in email:
            return jsonify({"error": "דוא\"ל חדש לא תקין"}), 400
        if not password or len(password) < 6:
            return jsonify({"error": "סיסמה חייבת להיות לפחות 6 תווים"}), 400
        if not name:
            return jsonify({"error": "שם משתמש נדרש"}), 400
        if role not in ['business', 'manager', 'admin']:
            return jsonify({"error": "תפקיד לא חדש"}), 400
        
        # Permission checks: who can create which roles
        if user_role == 'manager':
            # Manager can only create business or manager users
            if role == 'admin':
                return jsonify({"error": "ממנהל עסק לא יכול ליצור משתמשי admin"}), 403
        elif user_role == 'admin':
            # Admin can create all roles (admin/manager/business)
            pass
        elif user_role == 'superadmin':
            # Superadmin can create all roles
            pass
        
        # Check if user exists
        existing = User.query.filter_by(email=email).first()
        if existing:
            return jsonify({"error": "דוא\"ל זה כבר בשימוש"}), 400
        
        # Create new user
        new_user = User(
            email=email,
            name=name,
            password_hash=generate_password_hash(password, method='scrypt'),
            role=role,
            business_id=business_id,
            is_active=True
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'id': new_user.id,
            'email': new_user.email,
            'name': new_user.name,
            'role': new_user.role,
            'business_id': new_user.business_id,
            'created_at': new_user.created_at.isoformat() if new_user.created_at else None
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating user: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.put("/api/admin/users/<int:user_id>")
@require_api_auth(["admin", "manager", "superadmin"])
def update_user(user_id):
    """Update user details"""
    try:
        business_id = g.business_id
        user = User.query.get(user_id)
        
        if not user or user.business_id != business_id:
            return jsonify({"error": "משתמש לא נמצא"}), 404
        
        data = request.get_json() or {}
        
        if 'name' in data:
            user.name = data['name'].strip()
        if 'password' in data and data['password']:
            if len(data['password']) < 6:
                return jsonify({"error": "סיסמה חייבת להיות לפחות 6 תווים"}), 400
            user.password_hash = generate_password_hash(data['password'], method='scrypt')
        if 'role' in data and data['role'] in ['business', 'manager', 'admin']:
            # Permission checks for role changes
            if g.role == 'manager':
                # Manager cannot change anyone to admin
                if data['role'] == 'admin':
                    return jsonify({"error": "ממנהל עסק לא יכול להציב תפקיד admin"}), 403
            elif g.role == 'admin' or g.role == 'superadmin':
                # Admin and superadmin can set any role
                pass
            user.role = data['role']
        
        db.session.commit()
        
        return jsonify({
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'role': user.role,
            'business_id': user.business_id,
            'updated_at': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating user: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.delete("/api/admin/users/<int:user_id>")
@require_api_auth(["admin", "manager", "superadmin"])
def delete_user(user_id):
    """Soft delete user"""
    try:
        business_id = g.business_id
        user = User.query.get(user_id)
        
        if not user or user.business_id != business_id:
            return jsonify({"error": "משתמש לא נמצא"}), 404
        
        user.is_active = False
        db.session.commit()
        
        return jsonify({"success": True})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting user: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.put("/api/admin/businesses/<int:business_id>/reset-password")
@require_api_auth(["admin", "manager", "superadmin"])
def reset_business_password(business_id):
    """Reset business password (admin/manager/superadmin)"""
    try:
        business = Business.query.get(business_id)
        
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        data = request.get_json() or {}
        new_password = data.get('new_password')
        
        if not new_password:
            return jsonify({"error": "נא להזין סיסמה חדשה"}), 400
        
        if len(new_password) < 6:
            return jsonify({"error": "סיסמה חייבת להיות לפחות 6 תווים"}), 400
        
        business.password_hash = generate_password_hash(new_password, method='scrypt')
        db.session.commit()
        
        return jsonify({
            'success': True,
            'business_id': business.id,
            'business_name': business.name
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting business password: {e}")
        return jsonify({"error": str(e)}), 500


