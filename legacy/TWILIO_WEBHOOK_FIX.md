# 🔧 תיקון Twilio Webhook - הוראות דחופות

## ❌ בעיה נוכחית:
Twilio מנסה לגשת לנתיבים שגויים:
- `https://ai-crmd.replit.app/twilio/incoming_call` ❌
- `https://ai-crmd.replit.app/twilio/call_status` ❌

## ✅ הנתיבים הנכונים במערכת:
- `https://ai-crmd.replit.app/webhook/incoming_call` ✅
- `https://ai-crmd.replit.app/webhook/call_status` ✅

## 🛠️ תיקון דחוף נדרש ב-Twilio Console:

### שלב 1: כניסה ל-Twilio Console
1. היכנס ל: https://console.twilio.com/
2. לך ל: Phone Numbers > Manage > Active numbers
3. בחר את המספר: +97233763805

### שלב 2: עדכון Webhook URLs
**שנה את ה-Webhooks ל:**

**Voice Configuration:**
- Webhook URL: `https://ai-crmd.replit.app/webhook/incoming_call`
- HTTP Method: POST
- Fallback URL: `https://ai-crmd.replit.app/webhook/incoming_call`

**Call Status Events:**
- Status Callback URL: `https://ai-crmd.replit.app/webhook/call_status`
- HTTP Method: POST

### שלב 3: שמירה והפעלה
1. לחץ "Save Configuration"
2. המתן 30 שניות להפעלת השינויים
3. בצע שיחת בדיקה למספר +97233763805

## ✅ בדיקה שהמערכת עובדת:
המערכת כבר פועלת מצוין:
- TTS עברי Google WaveNet: פעיל ✅
- זיהוי עסק: פועל ✅
- יצירת הודעות קוליות: פועל ✅
- Response Status: 200 ✅

**לאחר התיקון השיחות יענו אוטומטית בעברית עם איכות קול מתקדמת!**