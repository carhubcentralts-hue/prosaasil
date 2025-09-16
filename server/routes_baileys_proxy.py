from flask import Blueprint, request, Response
import requests, os

bp_wa = Blueprint("wa_proxy", __name__)
BAILEYS_PORT = int(os.getenv("BAILEYS_PORT", "3300"))

@bp_wa.route("/wa/<path:path>", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"])
def wa_proxy(path):
    """Proxy all /wa/* requests to Baileys service running on localhost:BAILEYS_PORT"""
    url = f"http://127.0.0.1:{BAILEYS_PORT}/{path}"
    
    # מעבירים שיטה, גוף, כותרות רלוונטיות
    headers = {k:v for k,v in request.headers if k.lower() not in ("host","content-length")}
    
    try:
        resp = requests.request(
            request.method, 
            url, 
            params=dict(request.args),  # Convert MultiDict to dict
            data=request.get_data(), 
            headers=headers, 
            timeout=30
        )
        
        # מחזירים כמו שקיבלנו
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