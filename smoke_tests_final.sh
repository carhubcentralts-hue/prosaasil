#!/bin/bash
# Smoke Tests לפי ההנחיות המדויקות של המשתמש
# שלב E: login/csrf/impersonate/prompts עם status codes

set -e  # Stop on any error

# Configuration
BASE="http://localhost:5000"  # או PORT שהשרת רץ עליו
ADMIN_EMAIL="admin@shai-realestate.co.il"
ADMIN_PASSWORD="admin123"
COOKIE_FILE="/tmp/smoke_test_cookies"

echo "🧪 Starting AgentLocator CRM Smoke Tests..."
echo "📍 BASE URL: $BASE"

# Clean up previous test
rm -f $COOKIE_FILE

echo ""
echo "=== TEST 1: LOGIN ==="
echo "POST $BASE/api/auth/login"

LOGIN_RESPONSE=$(curl -s -i -c $COOKIE_FILE -b $COOKIE_FILE \
  -H 'Content-Type: application/json' \
  -X POST $BASE/api/auth/login \
  --data "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
  2>/dev/null)

echo "$LOGIN_RESPONSE"

# Check if login was successful (look for 200 status)
if echo "$LOGIN_RESPONSE" | grep -q "HTTP.*200"; then
    echo "✅ Login successful"
else
    echo "❌ Login failed"
    echo "Response: $LOGIN_RESPONSE"
    exit 1
fi

echo ""
echo "=== TEST 2: CSRF TOKEN ==="
echo "GET $BASE/api/auth/csrf"

# Get CSRF token
TOKEN=$(curl -s -c $COOKIE_FILE -b $COOKIE_FILE $BASE/api/auth/csrf | python3 - <<'PY'
import sys,json
try:
    data = json.load(sys.stdin)
    print(data['csrfToken'])
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PY
)

if [ -n "$TOKEN" ]; then
    echo "✅ CSRF token received: ${TOKEN:0:16}..."
else
    echo "❌ Failed to get CSRF token"
    curl -s -c $COOKIE_FILE -b $COOKIE_FILE $BASE/api/auth/csrf
    exit 1
fi

echo ""
echo "=== TEST 3: IMPERSONATE (צפוי 200) ==="
echo "POST $BASE/api/admin/businesses/1/impersonate"

IMPERSONATE_RESPONSE=$(curl -s -i -c $COOKIE_FILE -b $COOKIE_FILE \
  -H "X-CSRFToken: $TOKEN" \
  -X POST $BASE/api/admin/businesses/1/impersonate \
  2>/dev/null)

echo "$IMPERSONATE_RESPONSE"

if echo "$IMPERSONATE_RESPONSE" | grep -q "HTTP.*200"; then
    echo "✅ Impersonation successful"
elif echo "$IMPERSONATE_RESPONSE" | grep -q "403"; then
    echo "❌ 403 Forbidden - Check Guard logic (role/scope/OPTIONS)"
    echo "Error details:"
    echo "$IMPERSONATE_RESPONSE" | grep -E '{"error"|{"reason"' || echo "No JSON error found"
    exit 1
else
    echo "❌ Impersonation failed"
    echo "Response: $IMPERSONATE_RESPONSE"
    exit 1
fi

echo ""
echo "=== TEST 4: SAVE PROMPTS AFTER IMPERSONATION (צפוי 200) ==="
echo "PUT $BASE/api/business/current/prompt"

# Get fresh CSRF token from cookies (since SeaSurf updates it)
TOKEN_FRESH=$(grep '_csrf_token' $COOKIE_FILE | cut -f7)
if [ -z "$TOKEN_FRESH" ]; then
    TOKEN_FRESH=$TOKEN  # fallback to original token
fi

PROMPTS_RESPONSE=$(curl -s -i -c $COOKIE_FILE -b $COOKIE_FILE \
  -H "X-CSRFToken: $TOKEN_FRESH" \
  -H 'Content-Type: application/json' \
  -X PUT $BASE/api/business/current/prompt \
  --data '{"calls_prompt":"smoke test ok after impersonation","whatsapp_prompt":"smoke test ok after impersonation"}' \
  2>/dev/null)

echo "$PROMPTS_RESPONSE"

if echo "$PROMPTS_RESPONSE" | grep -q "HTTP.*200"; then
    echo "✅ Prompts saved successfully after impersonation"
else
    echo "❌ Prompts save failed"
    if echo "$PROMPTS_RESPONSE" | grep -q "403"; then
        echo "❌ 403 Forbidden - CSRF token issue"
        echo "Error details:"
        echo "$PROMPTS_RESPONSE" | grep -E '{"error"|{"reason"' || echo "No JSON error found"
    elif echo "$PROMPTS_RESPONSE" | grep -q "לא נמצא מזהה עסק"; then
        echo "❌ Business ID not found - admin needs to impersonate first"
    fi
    echo "Full response: $PROMPTS_RESPONSE"
    exit 1
fi

echo ""
echo "🎉 ALL SMOKE TESTS PASSED!"
echo "✅ Authentication flow working"
echo "✅ CSRF protection configured correctly"  
echo "✅ Impersonation system functional"
echo "✅ Prompts API operational"
echo ""
echo "🚀 System ready for production use!"