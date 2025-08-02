# Twilio Webhook Configuration הגדרות

## הכתובת הנכונה לTwilio Console:

### Voice Webhook (שיחות נכנסות):
```
https://carhubcentralts-workspace.replit.app/voice
```

### אלטרנטיבה (תומכת בשני הנתיבים):
```
https://carhubcentralts-workspace.replit.app/voice/incoming
```

## איך להגדיר:

1. **Twilio Console** → Phone Numbers → Manage → Active Numbers
2. **בחר את המספר הישראלי שלך** (+972...)
3. **Voice Configuration:**
   - A call comes in: **Webhook**
   - URL: `https://carhubcentralts-workspace.replit.app/voice`
   - HTTP: **POST**
4. **שמור**

## מה קורה כשמתקשרים:
1. שיחה נכנסת → `/voice`
2. ברכה בעברית
3. הקלטה של המתקשר (30 שניות)
4. תמלול Whisper + GPT + תגובה עברית
5. תשובה למתקשר

## ✅ הרוט פעיל ועובד!