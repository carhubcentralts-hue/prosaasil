"""
Enterprise Pagination & Performance Utils
מערכת עמוד וביצועים ברמה אנטרפרייז
"""
from flask import request, jsonify
from math import ceil

class PaginationMixin:
    """Mixin for consistent pagination across all models"""
    
    @classmethod
    def paginate_query(cls, query, page=None, per_page=25):
        """Universal pagination with performance optimizations"""
        page = page or int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', per_page)), 100)  # Max 100 items
        
        # Count total items (optimize with explain if needed)
        total = query.count()
        
        # Apply pagination
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return {
            'items': items,
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': ceil(total / per_page),
            'has_prev': page > 1,
            'has_next': page < ceil(total / per_page),
            'prev_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < ceil(total / per_page) else None
        }

def render_pagination_controls(pagination_data, endpoint, **kwargs):
    """Render consistent pagination controls for HTMX"""
    if pagination_data['pages'] <= 1:
        return ""
        
    html_parts = ['<nav class="flex items-center justify-between border-t border-gray-200 bg-white px-4 py-3 sm:px-6" aria-label="Pagination">']
    
    # Info
    html_parts.append(f'<div class="hidden sm:block"><p class="text-sm text-gray-700">מציג <span class="font-medium">{((pagination_data["page"] - 1) * pagination_data["per_page"]) + 1}</span> עד <span class="font-medium">{min(pagination_data["page"] * pagination_data["per_page"], pagination_data["total"])}</span> מתוך <span class="font-medium">{pagination_data["total"]}</span> תוצאות</p></div>')
    
    # Navigation
    html_parts.append('<div class="flex flex-1 justify-between sm:justify-end">')
    
    # Previous button
    if pagination_data['has_prev']:
        prev_url = f"{endpoint}?page={pagination_data['prev_page']}"
        for k, v in kwargs.items():
            if v:
                prev_url += f"&{k}={v}"
        html_parts.append(f'<button hx-get="{prev_url}" hx-target="#main-content" hx-indicator="#loading" class="relative inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">קודם</button>')
    else:
        html_parts.append('<button disabled class="relative inline-flex items-center rounded-md border border-gray-300 bg-gray-100 px-4 py-2 text-sm font-medium text-gray-400 cursor-not-allowed">קודם</button>')
    
    # Next button  
    if pagination_data['has_next']:
        next_url = f"{endpoint}?page={pagination_data['next_page']}"
        for k, v in kwargs.items():
            if v:
                next_url += f"&{k}={v}"
        html_parts.append(f'<button hx-get="{next_url}" hx-target="#main-content" hx-indicator="#loading" class="relative ml-3 inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">הבא</button>')
    else:
        html_parts.append('<button disabled class="relative ml-3 inline-flex items-center rounded-md border border-gray-300 bg-gray-100 px-4 py-2 text-sm font-medium text-gray-400 cursor-not-allowed">הבא</button>')
        
    html_parts.append('</div></nav>')
    
    return ''.join(html_parts)

def get_search_params():
    """Extract search parameters from request"""
    return {
        'q': request.args.get('q', '').strip(),
        'status': request.args.get('status', ''),
        'role': request.args.get('role', ''),
        'business_id': request.args.get('business_id', ''),
        'sort': request.args.get('sort', 'created_desc'),
        'page': int(request.args.get('page', 1))
    }

def build_filters_for_model(model, search_params, allowed_fields):
    """Build SQLAlchemy filters from search parameters"""
    filters = []
    
    # Text search
    if search_params.get('q'):
        q = f"%{search_params['q']}%"
        text_filters = []
        for field in allowed_fields.get('text', []):
            if hasattr(model, field):
                text_filters.append(getattr(model, field).ilike(q))
        if text_filters:
            from sqlalchemy import or_
            filters.append(or_(*text_filters))
    
    # Exact match filters
    for param_name, field_name in allowed_fields.get('exact', {}).items():
        if search_params.get(param_name) and hasattr(model, field_name):
            filters.append(getattr(model, field_name) == search_params[param_name])
    
    return filters

def apply_sorting(query, model, sort_param, allowed_sorts):
    """Apply sorting to query with performance optimizations"""
    if sort_param not in allowed_sorts:
        sort_param = 'created_desc'  # Default
    
    if sort_param.endswith('_desc'):
        field = sort_param[:-5]
        if hasattr(model, field):
            return query.order_by(getattr(model, field).desc())
    else:
        field = sort_param
        if hasattr(model, field):
            return query.order_by(getattr(model, field).asc())
    
    # Default fallback
    if hasattr(model, 'created_at'):
        return query.order_by(model.created_at.desc())
    elif hasattr(model, 'id'):
        return query.order_by(model.id.desc())
    
    return query