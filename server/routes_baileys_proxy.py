from flask import Blueprint, request, Response
import requests, os

bp_wa = Blueprint("wa_proxy", __name__)
BAILEYS_PORT = int(os.getenv("BAILEYS_PORT", "3300"))

# SECURITY: Whitelist-only proxy - block dangerous endpoints like /send
ALLOWED_PATHS = {"health", "qr"}

@bp_wa.route("/wa/<path:path>", methods=["GET", "OPTIONS"])
def wa_proxy(path):
    """
    SECURE proxy for Baileys service - only allow safe read-only endpoints
    /wa/send is BLOCKED to prevent unauthorized message sending
    """
    # Security check: only allow whitelisted paths
    if path not in ALLOWED_PATHS:
        print(f"🚫 Blocked Baileys proxy access to: /wa/{path}")
        return Response(
            '{"error":"forbidden","message":"Endpoint not allowed via proxy"}',
            status=403,
            headers=[('Content-Type', 'application/json')]
        )
    
    # Only allow GET requests for safety
    if request.method != "GET":
        print(f"🚫 Blocked Baileys proxy {request.method} to: /wa/{path}")
        return Response(
            '{"error":"method_not_allowed","message":"Only GET requests allowed"}',
            status=405,
            headers=[('Content-Type', 'application/json')]
        )
    
    url = f"http://127.0.0.1:{BAILEYS_PORT}/{path}"
    
    try:
        resp = requests.get(
            url, 
            params=dict(request.args),
            timeout=10  # Shorter timeout for safety
        )
        
        # Return response safely
        excluded = {"content-encoding","transfer-encoding","connection"}
        headers_out = [(k,v) for k,v in resp.headers.items() if k.lower() not in excluded]
        
        return Response(resp.content, status=resp.status_code, headers=headers_out)
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Baileys proxy error: {e}")
        return Response(
            '{"error":"baileys_unavailable","message":"Baileys service not reachable"}',
            status=503,
            headers=[('Content-Type', 'application/json')]
        )