#!/bin/bash
# בדיקות GO/NO-GO לפי ההנחיות

echo "=== בדיקת WhatsApp API ==="
echo ""

echo "1️⃣ בדיקת /api/whatsapp/start"
curl -sS -i -X POST http://127.0.0.1:5000/api/whatsapp/start | head -20
echo ""

echo "2️⃣ בדיקת /api/whatsapp/status (לפני סריקה)"
curl -sS http://127.0.0.1:5000/api/whatsapp/status | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2, ensure_ascii=False))"
echo ""

echo "3️⃣ בדיקת /api/whatsapp/qr"
QR_RESPONSE=$(curl -sS http://127.0.0.1:5000/api/whatsapp/qr)
echo "$QR_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Has dataUrl: {d.get('dataUrl') is not None}, Has qrText: {d.get('qrText') is not None}\")"
echo ""

echo "4️⃣ בדיקת קבצים ב-storage"
ls -la storage/whatsapp/business_1/auth/ 2>/dev/null || echo "❌ אין תיקיית auth"
echo ""

echo "=== בדיקת Prompts API ==="
echo ""

echo "5️⃣ קבלת CSRF + Login"
CSRF=$(curl -sS http://127.0.0.1:5000/api/auth/csrf -c /tmp/test_cookies.txt | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['csrfToken'])")
curl -sS "http://127.0.0.1:5000/api/auth/login" -X POST \
  -H "X-CSRFToken: $CSRF" \
  -H "Content-Type: application/json" \
  -b /tmp/test_cookies.txt \
  -c /tmp/test_cookies.txt \
  -d '{"email":"admin@shai-realestate.co.il","password":"admin123"}' > /dev/null
CSRF_NEW=$(grep csrf /tmp/test_cookies.txt | awk '{print $7}')
echo "✅ Logged in, CSRF: ${CSRF_NEW:0:20}..."
echo ""

echo "6️⃣ קריאת Prompt נוכחי"
curl -sS "http://127.0.0.1:5000/api/business/current/prompt" \
  -H "X-CSRFToken: $CSRF_NEW" \
  -b /tmp/test_cookies.txt | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Calls: {d.get('calls_prompt', 'N/A')[:50]}...\"); print(f\"WhatsApp: {d.get('whatsapp_prompt', 'N/A')[:50]}...\")"
echo ""

echo "7️⃣ שמירת Prompt חדש"
curl -sS "http://127.0.0.1:5000/api/business/current/prompt" -X PUT \
  -H "X-CSRFToken: $CSRF_NEW" \
  -H "Content-Type: application/json" \
  -b /tmp/test_cookies.txt \
  -d '{"calls_prompt":"בדיקה אוטומטית טלפון ✅","whatsapp_prompt":"בדיקה אוטומטית וואטסאפ ✅"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ Success!' if d.get('success') or d.get('message') else f\"❌ {d}\")"
echo ""

echo "=== בדיקת Twilio Webhook ==="
echo ""

echo "8️⃣ טסט webhook (ללא חתימה)"
curl -sS -i -X POST http://127.0.0.1:5000/webhook/twilio/voice \
  -d "CallSid=CA_test&From=+1555&To=+1555" | head -20
echo ""

echo "✅ סיימתי בדיקות - בדוק את הפלט למעלה"
