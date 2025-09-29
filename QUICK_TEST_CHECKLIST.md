# 🚀 צ'ק-ליסט בדיקה מהירה - Build #59

## בצע בדיוק לפי הסדר הזה:

### 1️⃣ פרומפטים - בדיקת API ישירה
```bash
curl -i -sS -X POST http://127.0.0.1:5000/api/business/business_1/prompts \
  -H 'Content-Type: application/json' \
  --data '{"title":"sanity","body":"ok"}'
```
**צפוי:** `{"ok": true, "id": 1}` + HTTP 200

### 2️⃣ וואטסאפ - 4 בדיקות (לפני/אחרי סריקה)
```bash
# Status - צריך להחזיר JSON עם connected/hasQR
curl -i -sS http://127.0.0.1:5000/api/whatsapp/status | head -10

# QR - צריך להחזיר qrText או dataUrl
curl -i -sS http://127.0.0.1:5000/api/whatsapp/qr | head -10

# Start - צריך להחזיר {"ok": true}
curl -i -sS -X POST http://127.0.0.1:5000/api/whatsapp/start

# בדוק שהתיקיות מסונכרנות:
ls -la storage/whatsapp/business_1/auth
```

### 3️⃣ שיחות - סימולצית קריאה נכנסת
```bash
curl -i -sS -X POST http://127.0.0.1:5000/webhook/twilio/voice \
  -d "CallSid=CA_test&From=+1555&To=+1555"
```
**צפוי:** TwiML (XML response) + HTTP 200

### 4️⃣ בדיקה מהירה (30 שניות)
```bash
echo "=== Build #59 Health Check ==="
echo -n "API Status: "; curl -s http://127.0.0.1:5000/api/whatsapp/status | jq -r '.connected // "ERROR"' 2>/dev/null || echo "JSON_ERROR"
echo -n "QR Available: "; curl -s http://127.0.0.1:5000/api/whatsapp/qr | jq -r 'has("qrText") // "ERROR"' 2>/dev/null || echo "JSON_ERROR"  
echo -n "DB Connection: "; python3 -c "from server.models_sql import Customer; print('OK -', Customer.query.count(), 'customers')" 2>/dev/null || echo "DB_ERROR"
echo "=== End Check ==="
```

---

## 📊 תוצאות צפויות:

✅ **GO אם:**
- כל ה-curl מחזירים HTTP 200
- JSON תקני (לא HTML errors)
- Status/QR מחזירים מבנה נכון
- DB מחזיר מספר לקוחות

❌ **NO-GO אם:**
- שגיאות 500/400 ב-API
- HTML במקום JSON
- "JSON_ERROR" או "DB_ERROR" בבדיקה המהירה
- שיחות לא מחזירות XML תקני

---

## 🔧 תיקונים שבוצעו - Build #59:
1. ✅ **API Handler** - JSON יציב עם commit/rollback
2. ✅ **Tenant אחיד** - business_1 ב-Node ו-Flask  
3. ✅ **QR יציב** - כתיבה/מחיקה נכונה של qr_code.txt
4. ✅ **Start כפול** - מניעת קריאות כפולות
5. ✅ **JSON תמידי** - כל /api/whatsapp/* מחזיר JSON
6. ✅ **לידים אוטומטיים** - כל שיחה → ליד במסד הנתונים
7. ✅ **Runner יציב** - start_production.sh עם trap+cleanup

המערכת מוכנה לפרסום!