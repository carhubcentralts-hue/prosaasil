# 🚀 מדריך התחלה מהירה - מערכת שיחות עברית עם לאה

## 📁 הקבצים שקיבלת:

### 1. **COMPLETE_CALL_SYSTEM.py** - הקוד המלא
- 🤖 כל הקוד של לאה (Hebrew AI Agent)  
- 📞 Twilio Media Streams handler
- 🎙️ Google STT/TTS עברית
- ⚡ VAD מותאם לעברית + Barge-in handling
- 🧠 מניעת לולאות + זיכרון 10 תשובות

### 2. **HEBREW_AI_CONFIG.env** - כל ההגדרות
- 🔑 מקומות ל-API keys (OpenAI, Twilio, Google Cloud)
- 📞 מספרי טלפון וכתובת שרת
- 🎛️ כל הפרמטרים של VAD, AI, TTS
- 🏢 הגדרות עסקיות של החברה

### 3. **INSTALL_REQUIREMENTS.txt** - דרישות התקנה
- 📦 כל החבילות הנדרשות
- 🔧 הוראות התקנה מפורטות
- 🌐 הגדרת Google Cloud + Twilio + OpenAI
- 🚀 אפשרויות deployment

---

## ⚡ התחלה מהירה (5 דקות):

### 1. הכן את הסביבה:
```bash
# צור virtual environment
python -m venv hebrew-ai
source hebrew-ai/bin/activate  # Linux/Mac
# hebrew-ai\Scripts\activate   # Windows

# התקן dependencies
pip install -r INSTALL_REQUIREMENTS.txt
```

### 2. הגדר API Keys:
- העתק `HEBREW_AI_CONFIG.env` ל-`.env` 
- מלא את כל ה-API keys:
  - `OPENAI_API_KEY` - מ-OpenAI
  - `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` - מ-Twilio
  - `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` - מ-Google Cloud

### 3. בדוק שהכל עובד:
```python
python COMPLETE_CALL_SYSTEM.py
```
אמור לראות: ✅ All required environment variables are set

### 4. הפעל שרת:
```python
from COMPLETE_CALL_SYSTEM import example_flask_integration
app = example_flask_integration()
app.run(host='0.0.0.0', port=5000)
```

### 5. הגדר Twilio Webhook:
בTwilio Console, הגדר:
- **Voice URL:** `https://yourdomain.com/webhook/incoming_call`
- **Method:** POST

---

## 🎯 מה לאה תעשה בשיחה:

1. **ברכה:** "שלום! אני לאה משי דירות ומשרדים. איך אני יכולה לעזור?"
2. **האזנה חכמה:** 1.5 שניות דיבור רציף לפני שמבינה שאתה מדבר
3. **תגובות קצרות:** מקסימום 15 מילים, שאלה אחת
4. **זיכרון:** זוכרת 10 ההחלפות האחרונות
5. **הגנה:** לא תפריע לך, לא תעצור באמצע תגובה שלה

---

## 📞 בדיקה מהירה:

1. הפעל השרת
2. התקשר למספר Twilio שלך
3. אמור: "שלום, אני מחפש דירה"  
4. לאה תשאל: "באיזה אזור אתה מעוניין?"

---

## 🔧 התאמות נפוצות:

### שינוי הברכה:
```python
# בקובץ COMPLETE_CALL_SYSTEM.py, שורה ~430
greet = "הברכה החדשה שלך כאן"
```

### שינוי threshold של VAD:
```python  
# בקובץ .env
VAD_RMS=250  # גבוה יותר = פחות רגיש
```

### הוספת מילים לזיהוי:
```python
# בפונקציה _hebrew_stt, הוסף למערך phrases
"המילה החדשה", "ביטוי נוסף"
```

---

## 🚨 בעיות נפוצות:

**שגיאה: "No module named 'audioop'"**
```bash
pip install --upgrade python  # צריך Python 3.9+
```

**שגיאה: Google Cloud authentication**
```bash
# הוסף למשתני הסביבה:
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"
```

**WebSocket מתנתק:**
- בדוק שהשרת supports WebSocket
- הפעל עם gunicorn + eventlet: `gunicorn -k eventlet wsgi:app`

---

## 💰 עלויות משוערות (לדקה):
- OpenAI: $0.01-0.02
- Google STT: $0.016  
- Google TTS: $0.016
- Twilio: $0.0085
- **סה"כ: ~$0.05-0.07 לדקה**

---

## 🎯 לאה מוכנה!

כל הקוד הקריטי נמצא ב-`COMPLETE_CALL_SYSTEM.py` - זה הקובץ הראשי שמכיל הכל.
עם ההגדרות ב-`.env` והדרישות ב-`requirements.txt` יש לך מערכת מלאה!