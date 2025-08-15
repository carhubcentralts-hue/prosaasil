"""
מערכת Pagination אחידה לכל CRM APIs
החזרת מבנה עקבי: {results, page, pages, total}
"""
from flask import request
from math import ceil

def paginate_query(query_or_list, page=None, limit=None):
    """
    Paginate SQLAlchemy query או רשימה רגילה
    מחזיר: (results, page, pages, total)
    """
    page = page or int(request.args.get("page", 1))
    limit = limit or int(request.args.get("limit", 25))
    
    # וודא ערכים חוקיים
    page = max(1, page)
    limit = min(max(1, limit), 100)  # מגביל עד 100 פריטים בעמוד
    
    if hasattr(query_or_list, 'count'):
        # SQLAlchemy Query
        total = query_or_list.count()
        results = query_or_list.offset((page - 1) * limit).limit(limit).all()
    else:
        # רשימה רגילה
        total = len(query_or_list)
        start = (page - 1) * limit
        end = start + limit
        results = query_or_list[start:end]
    
    pages = ceil(total / limit) if limit > 0 else 1
    
    return results, page, pages, total

def pagination_response(results, page, pages, total):
    """מבנה תגובה אחיד לכל API endpoints"""
    return {
        "results": results,
        "page": page,
        "pages": pages,
        "total": total
    }

def get_pagination_params():
    """שליפת פרמטרי pagination מה-request"""
    return {
        "page": int(request.args.get("page", 1)),
        "limit": int(request.args.get("limit", 25)),
        "q": request.args.get("q", "").strip()  # חיפוש טקסט
    }