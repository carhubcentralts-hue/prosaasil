"""
Multi-tenant Payment Providers with Simulation Support
BYO (Bring Your Own) keys per business
"""
import os
import requests
import json
from urllib.parse import urlencode

class PayResult:
    def __init__(self, ok, data=None, error=""):
        self.ok, self.data, self.error = ok, (data or {}), error

def sys_enabled() -> bool:
    """Check if payments are globally enabled"""
    return os.getenv("PAYMENTS_ENABLED","false").lower() in ("1","true","yes","on")

def _is_on(biz) -> bool:
    """Check if payments are enabled for specific business"""
    return sys_enabled() and bool(biz and biz.payments_enabled)

# -------- NO-OP (סימולציה) --------
def noop_create(amount_agorot: int, currency: str, payment_id: int) -> PayResult:
    """Simulation mode - internal redirect, no external API calls"""
    return PayResult(True, {
        "redirect_url": f"/api/crm/__payments/mock?payment_id={payment_id}&amount={amount_agorot}&currency={currency}"
    }, "payments disabled; noop")

# -------- PayPal --------
def _pp_base(mode: str):
    return "https://api-m.sandbox.paypal.com" if mode != "live" else "https://api-m.paypal.com"

def _pp_token(client_id: str, secret: str, mode: str):
    r = requests.post(_pp_base(mode) + "/v1/oauth2/token", 
                      auth=(client_id, secret),
                      data={"grant_type": "client_credentials"})
    r.raise_for_status()
    return r.json()["access_token"]

def paypal_create_order(biz, gw, amount_agorot: int, currency: str, payment_id: int) -> PayResult:
    if not _is_on(biz):
        return noop_create(amount_agorot, currency, payment_id)
    if not (gw and gw.paypal_client_id and gw.paypal_secret):
        return PayResult(False, error="paypal keys missing for this business")
    
    try:
        access = _pp_token(gw.paypal_client_id, gw.paypal_secret, gw.mode or "sandbox")
        value = f"{amount_agorot/100:.2f}"
        j = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {"currency_code": currency.upper(), "value": value},
                "custom_id": f"{biz.id}:{payment_id}"   # For webhook business/payment recovery
            }],
            "application_context": {"shipping_preference": "NO_SHIPPING"}
        }
        r = requests.post(_pp_base(gw.mode) + "/v2/checkout/orders",
                          headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
                          json=j)
        r.raise_for_status()
        data = r.json()
        approve = next((l["href"] for l in data.get("links", []) if l.get("rel") == "approve"), None)
        return PayResult(True, {"order_id": data["id"], "approve_url": approve})
    except Exception as e:
        return PayResult(False, error=f"PayPal API error: {e}")

# -------- Tranzila (Redirect/iFrame) --------
def tranzila_create_link(biz, gw, amount_agorot: int, currency: str, payment_id: int) -> PayResult:
    if not _is_on(biz):
        return noop_create(amount_agorot, currency, payment_id)
    if not (gw and gw.tranzila_terminal):
        return PayResult(False, error="tranzila terminal missing for this business")
    
    base = f"https://direct.tranzila.com/{gw.tranzila_terminal}/iframenew.php"
    params = {
        "sum": f"{amount_agorot/100:.2f}",
        "currency": currency,
        "success_url": os.getenv("TRANZILA_RETURN_SUCCESS", "https://ai-crmd.replit.app/api/crm/payments/tranzila/return/success"),
        "fail_url": os.getenv("TRANZILA_RETURN_FAIL", "https://ai-crmd.replit.app/api/crm/payments/tranzila/return/fail"),
        "notify_url": os.getenv("TRANZILA_NOTIFY_URL", "https://ai-crmd.replit.app/api/crm/payments/tranzila/notify"),
        "lang": "he",
        "ordernum": str(payment_id),    # Our internal payment ID
        "udf": str(biz.id)              # Business ID for webhook recovery
    }
    return PayResult(True, {"redirect_url": base + "?" + urlencode(params)})

# -------- Universal Router --------
def create_payment_link(biz, gw, provider: str, amount_agorot: int, currency: str, payment_id: int) -> PayResult:
    """Main entry point for payment link creation"""
    p = (provider or (biz.default_provider if biz else "paypal")).lower()
    if p == "paypal":
        return paypal_create_order(biz, gw, amount_agorot, currency, payment_id)
    elif p == "tranzila":
        return tranzila_create_link(biz, gw, amount_agorot, currency, payment_id)
    else:
        return noop_create(amount_agorot, currency, payment_id)