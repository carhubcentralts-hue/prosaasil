# הנחיות הגדרת Twilio - מערכת שיחות עברית AI

## ✅ המערכת מוכנה! צריך רק להגדיר את Twilio

### 1. כתובות Webhook שצריך להגדיר ב-Twilio:

**Voice Webhook (שיחות נכנסות):**
```
https://ai-crmd.replit.app/webhook/incoming_call
Method: POST
```

**Status Callback (עדכוני סטטוס):**
```
https://ai-crmd.replit.app/webhook/call_status
Method: POST
```

**Recording Webhook (עיבוד הקלטות):**
```
https://ai-crmd.replit.app/webhook/handle_recording
Method: POST
```

### 2. איך להגדיר ב-Twilio Console:

1. **היכנס ל-Twilio Console** → Phone Numbers → Manage → Active numbers
2. **בחר את המספר** שרוצה להגדיר
3. **Voice Configuration:**
   - Webhook: `https://ai-crmd.replit.app/webhook/incoming_call`
   - HTTP Method: POST
   - Status Callback: `https://ai-crmd.replit.app/webhook/call_status`
4. **שמור את השינויים**

### 3. בדיקת תקינות הגדרות:

```bash
# בדיקת webhook שיחות נכנסות:
curl -X POST "https://ai-crmd.replit.app/webhook/incoming_call" \
  -d "CallSid=TEST&From=%2B972501234567&To=%2B972501234567"

# בדיקת webhook סטטוס:
curl -X POST "https://ai-crmd.replit.app/webhook/call_status" \
  -d "CallSid=TEST&CallStatus=completed"
```

### 4. מה יקרה בשיחה:

1. **שיחה נכנסת** → ברכה בעברית (welcome.mp3)
2. **הקלטת לקוח** → תמלול Whisper בעברית  
3. **תגובת AI** → GPT-4o בעברית לנדל"ן
4. **TTS עברית** → יצירת קובץ MP3 איכותי
5. **המשך שיחה** → העוז כל זה שוב

### 5. לוגים וניטור:

המערכת מתעדת כל שיחה עם:
- Request-ID tracking
- Hebrew transcription logs  
- AI response logs
- TTS generation logs
- מיסוך מספרי טלפון (9****67)

### 6. אם עדיין לא עובד:

- ✅ ודא שה-webhook URLs מוגדרים נכון
- ✅ בדוק שהמספר Twilio מוגדר לשימוש
- ✅ התקשר למספר עצמו ובדוק logs
- ✅ ודא שהאפליקציה פועלת על ai-crmd.replit.app

## 🎯 סיכום: המערכת מוכנה לשימוש!

כל הרכיבים הטכניים עובדים. צריך רק להגדיר את Twilio לשלוח שיחות לכתובות הנכונות.