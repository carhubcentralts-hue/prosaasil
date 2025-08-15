#!/usr/bin/env python3
"""
בדיקת ראוטים לזיהוי כפילויות והתנגשויות
"""

def print_routes(app):
    """Print all Flask routes and check for duplicates"""
    seen = {}
    duplicates = []
    
    print("=== Flask Routes Map ===")
    for r in sorted(app.url_map.iter_rules(), key=lambda x: (x.rule, ",".join(sorted(x.methods)))):
        if r.endpoint.startswith("static"):
            continue
            
        methods = tuple(sorted([m for m in r.methods if m in {"GET","POST","PUT","DELETE","PATCH"}]))
        sig = (r.rule, methods)
        
        print(f"{r.rule:30} {str(methods):20} -> {r.endpoint}")
        
        if sig in seen:
            duplicates.append((sig, seen[sig], r.endpoint))
            print(f"*** DUPLICATE ROUTE: {sig} => {seen[sig]} and {r.endpoint} ***")
        else:
            seen[sig] = r.endpoint
    
    print(f"\n=== Summary ===")
    print(f"Total routes: {len(seen)}")
    print(f"Duplicates found: {len(duplicates)}")
    
    if duplicates:
        print("\n🚨 DUPLICATE ROUTES DETECTED:")
        for sig, endpoint1, endpoint2 in duplicates:
            print(f"  {sig} -> {endpoint1} AND {endpoint2}")
        return False
    else:
        print("✅ No duplicate routes found")
        return True

if __name__ == "__main__":
    from server.app_factory import create_app
    app = create_app()
    
    with app.app_context():
        routes_ok = print_routes(app)
        if not routes_ok:
            exit(1)
        print("✅ Routes validation passed")