# 🎵 Google Cloud TTS Setup Guide

## צעדים להפעלת Google Cloud Hebrew TTS:

### 1. הורד את קובץ ה-JSON
- בדף שהראית, לחץ על השורה של המפתח (bbfa7a03d9043336da...)
- תמצא אופציה "Download" או שלוש נקודות ואז "Download"
- זה יוריד קובץ JSON למחשב שלך

### 2. פתח את הקובץ
- פתח את הקובץ שהורדת (יהיה שם כמו `tts-service-bbfa7a03d904.json`)
- תראה תוכן כזה:
```json
{
  "type": "service_account",
  "project_id": "manifest-alpha-465212-r7",
  "private_key_id": "bbfa7a03d9043336da684f91465f185ab6bb85ec",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQI....\n-----END PRIVATE KEY-----\n",
  "client_email": "tts-service@manifest-alpha-465212-r7.iam.gserviceaccount.com",
  ...
}
```

### 3. העתק את כל התוכן
- בחר הכל (Ctrl+A)
- העתק (Ctrl+C)

### 4. עדכן ב-Replit
- לך ל-Replit Secrets (בצד שמאל)
- מצא `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON`
- מחק את התוכן הנוכחי (`manifest-alpha-465212-r7-bbfa7a03d904.json`)
- הדבק את כל תוכן ה-JSON שהעתקת

### 5. אתחל את המערכת
המערכת תזהה את השינוי ותתחיל להשתמש ב-Google Cloud TTS במקום gTTS.

## תוצאה צפויה:
- קול עברי איכותי יותר (WaveNet)
- ביצועים טובים יותר
- קול יותר טבעי ומובן

## אם לא מצליח:
המערכת תמשיך לעבוד עם gTTS (שכבר עובד מושלם!)