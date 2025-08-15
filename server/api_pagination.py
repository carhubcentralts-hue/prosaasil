"""Unified pagination for all CRM endpoints"""

def get_pagination_params(request):
    """חילוץ פרמטרי pagination מהבקשה"""
    page = int(request.args.get('page', 1))
    limit = min(int(request.args.get('limit', 25)), 100)  # מקסימום 100
    return page, limit

def paginate_query(query, page: int, limit: int):
    """
    Unified pagination function that returns consistent structure
    Returns: results, page, pages, total
    """
    # Validate inputs
    page = max(1, page)
    limit = min(100, max(1, limit))  # Limit between 1-100
    
    # Get total count
    if hasattr(query, 'count') and callable(getattr(query, 'count')):
        # SQLAlchemy query
        total = query.count()
    else:
        # List or other iterable
        total = len(query)
    
    # Calculate pagination
    pages = (total + limit - 1) // limit  # Ceiling division
    
    # Get results for current page
    if hasattr(query, 'offset'):  # SQLAlchemy query
        results = query.offset((page - 1) * limit).limit(limit).all()
    else:  # List
        start = (page - 1) * limit
        end = start + limit
        results = query[start:end]
    
    return results, page, pages, total

def pagination_response(results, page, pages, total):
    """Create consistent pagination response"""
    return {
        "results": results,
        "page": page, 
        "pages": pages,
        "total": total
    }