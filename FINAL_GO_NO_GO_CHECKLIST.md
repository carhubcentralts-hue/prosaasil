# 🚀 AgentLocator - צ'ק-ליסט GO/NO-GO מעשי

## Pre-Flight: הפעלת המערכת
```bash
# 1. הפעל את המערכת
./start_all.sh

# חכה 10 שניות שהשירותים יעמדו
# בדוק שרואה: "Flask started (PID: XXX)" ו־"Baileys started (PID: YYY)"
```

---

## 🟢 בדיקה 1: API Routes - WhatsApp
```bash
# Status - חייב להחזיר JSON עם connected/hasQR
curl -s http://localhost:5000/api/whatsapp/status | jq '.'

# QR - צריך להחזיר dataUrl או qrText
curl -s http://localhost:5000/api/whatsapp/qr | jq '.'

# Contacts - צריך להחזיר רשימה (ולא 500)
curl -s http://localhost:5000/api/whatsapp/contacts?business_id=1 | jq '.'

# Messages - צריך להחזיר היסטוריה
curl -s http://localhost:5000/api/whatsapp/messages?business_id=1 | jq '.'

# Stats - צריך להחזיר מספרים
curl -s http://localhost:5000/api/whatsapp/stats?business_id=1 | jq '.'
```

**✅ GO תנאי:** כל הפקודות מחזירות 200 + JSON תקני (לא 500/404)  
**❌ NO-GO:** שגיאות 500 או תגובות HTML במקום JSON

---

## 🟢 בדיקה 2: פרומפטים + שמירה JSON יציבה
```bash
# שמור פרומפט חדש
curl -X POST http://localhost:5000/api/whatsapp/prompts/1 \
  -H "Content-Type: application/json" \
  -d '{"whatsapp_prompt": "שלום! אני לאה, הסוכנת הדיגיטלית"}' | jq '.'

# בדוק שנשמר (GET prompt)
curl -s http://localhost:5000/api/ai-prompt/1 | jq '.'
```

**✅ GO תנאי:** POST מחזיר `{"ok": true, "id": 1}` ו־GET מחזיר את הפרומפט  
**❌ NO-GO:** שגיאות 500 או איבוד מידע

---

## 🟢 בדיקה 3: דפדפן - UI עובד
```
1. פתח: http://localhost:5000
2. לחץ "WhatsApp Management" בתפריט
3. בדוק שרואה:
   ☐ Connection Status (Connected/Disconnected)  
   ☐ QR Code או הודעת "Already Connected"
   ☐ Message History Table (יכול להיות ריק)
   ☐ לא רואה שגיאות ב־Console (F12)
```

**✅ GO תנאי:** כל העמודים נטענים ללא שגיאות JavaScript  
**❌ NO-GO:** שגיאות בקונסול או דפים ריקים

---

## 🟢 בדיקה 4: Tenant אחיד - Baileys Storage
```bash
# בדוק איזה תיקיות קיימות:
ls -la storage/whatsapp/
ls -la baileys_auth_info/

# צריך להיות path אחד עקבי
# אם יש גם storage/whatsapp/1 וגם storage/whatsapp/business_1 → צריך לתקן
```

**✅ GO תנאי:** קיימת תיקייה אחת ברורה (לא כפילויות)  
**❌ NO-GO:** שתי תיקיות או confusion בנתיבים

---

## 🟢 בדיקה 5: Database Models + טבלאות
```bash
# בדוק שהטבלאות קיימות
python3 -c "
from server.models_sql import db, Customer, CallLog, WhatsAppMessage, Business
print('✅ Models imported successfully')
try:
    # נסה query פשוט
    count = Customer.query.count()
    print(f'✅ Customers table: {count} records')
except Exception as e:
    print(f'❌ DB Error: {e}')
"
```

**✅ GO תנאי:** "Models imported successfully" + מספר לקוחות  
**❌ NO-GO:** Import Error או Database Connection Failed

---

## 🟢 בדיקה 6: Twilio Webhooks (אופציונלי אם יש Ngrok)
```bash
# אם יש ngrok להרצה:
# ngrok http 5000

# בדוק ש־webhook endpoints מגיבים:
curl -X POST http://localhost:5000/webhook/incoming_call \
  -d "CallSid=test123&From=+972501234567" | head -1

# צריך להחזיר XML (TwiML) ולא שגיאה
```

**✅ GO תנאי:** תגובת XML תקנית מ־Twilio webhooks  
**❌ NO-GO:** שגיאות 500 או תגובות לא תקינות

---

## 🟢 בדיקה 7: יצירת לידים אוטומטית
```bash
# סימולצית קריאה נכנסת (בדיקת הלוגיקה):
python3 -c "
from server.routes_twilio import _create_lead_from_call
_create_lead_from_call('test_call_123', '+972501234567')
print('✅ Lead creation test completed')
"

# בדוק שנוצר Customer:
python3 -c "
from server.models_sql import Customer
c = Customer.query.filter_by(phone_e164='+972501234567').first()
if c:
    print(f'✅ Customer created: ID={c.id}, Name={c.name}')
else:
    print('❌ No customer found')
"
```

**✅ GO תנאי:** "Customer created: ID=X" מופיע  
**❌ NO-GO:** "No customer found" או שגיאות

---

## 📊 **דוח סופי - החלטה**

### ✅ GO לפרודקשן אם:
- [ ] כל 5 בדיקות API מחזירות 200 + JSON
- [ ] פרומפטים נשמרים ונטענים נכון  
- [ ] UI נטען ללא שגיאות JavaScript
- [ ] יש tenant אחד עקבי (לא כפילויות)
- [ ] Database מחובר ו־models עובדים
- [ ] לידים נוצרים אוטומטית מקריאות
- [ ] שירותי Baileys + Flask פועלים 5+ דקות ללא קריסות

### ❌ NO-GO (חזור לפיתוח) אם:
- [ ] יותר מ-1 API route מחזיר 500
- [ ] שגיאות JavaScript בדפדפן
- [ ] Database לא מחובר
- [ ] שירותים קורסים תוך דקה
- [ ] לידים לא נוצרים מקריאות
- [ ] כפילות בתיקיות storage

---

## 🎯 סיכום מהיר (30 שניות)
```bash
# הרץ את זה והכל צריך להיות ירוק:
echo "=== Quick Health Check ==="
curl -s http://localhost:5000/api/whatsapp/status | jq -r '.connected // "ERROR"'
curl -s http://localhost:5000/api/whatsapp/contacts?business_id=1 | jq -r 'type'
python3 -c "from server.models_sql import Customer; print('DB:', Customer.query.count(), 'customers')"
echo "=== End Check ==="
```

אם הכל ירוק → **🚀 GO לפרודקשן!**