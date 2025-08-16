# ✅ הוראות לבדיקת Twilio Console

## 📞 בדיקה 1: המספר הטלפון
בTwilio Console → Phone Numbers → Manage → Active Numbers

1. **מה המספר שאתה רואה שם?**
2. **לחץ על המספר**

## 🌐 בדיקה 2: הWebhook
במסך המספר, תחת **Voice & Fax**:

1. **A call comes in**: צריך להיות "Webhook"
2. **URL**: צריך להיות **בדיוק**: `https://ai-crmd.replit.app/webhook/incoming_call`
3. **HTTP Method**: צריך להיות "POST"

## 🔍 בדיקה 3: הכתובת
**תעתיק בדיוק את הURL שרשום שם ותשלח לי אותו**

## ⚠️ בעיות נפוצות:
- URL עם תווים מיוחדים
- HTTP במקום HTTPS  
- trailing slash (/) בסוף
- domain שונה

**אחרי שתבדוק, תגיד לי מה כתוב שם בדיוק!**