# מדריך מהיר - איפה להוסיף ENCRYPTION_KEY
# Quick Guide - Where to Add ENCRYPTION_KEY

## 📍 מיקום הקובץ / File Location

```
prosaasil/
├── .env                    ← 🎯 הוסף את ENCRYPTION_KEY כאן!
├── .env.example           ← דוגמה (אל תשנה)
└── docker-compose.yml     ← משתמש ב-.env
```

## 🔧 שלבים / Steps

### 1️⃣ צור מפתח / Generate Key

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**פלט לדוגמה / Example output:**
```
xQz8K9vW2nF5mL7pT3gH1jR6dS4yA8bC0eU9iO5qN2k=
```

### 2️⃣ פתח את הקובץ .env / Open .env file

```bash
nano /path/to/prosaasil/.env
# או / or
vim /path/to/prosaasil/.env
```

### 3️⃣ הוסף את השורה / Add the line

```bash
# Gmail OAuth Encryption Key
ENCRYPTION_KEY=xQz8K9vW2nF5mL7pT3gH1jR6dS4yA8bC0eU9iO5qN2k=
```

⚠️ **חשוב / Important:** השתמש במפתח שיצרת בשלב 1, לא בדוגמה למעלה!
Use the key YOU generated in step 1, not the example above!

### 4️⃣ הפעל מחדש / Restart

```bash
cd /path/to/prosaasil
docker-compose down
docker-compose up -d
```

### 5️⃣ בדוק / Verify

```bash
# בדוק שאין שגיאות / Check for errors
docker-compose logs prosaas-backend | grep -i encryption
```

אם הכל תקין, לא אמור להיות פלט / If OK, should be no output

---

## 📋 דוגמה מלאה לקובץ .env / Full .env Example

```bash
# ... שאר ההגדרות / other settings ...

# ===========================================
# GMAIL RECEIPTS INTEGRATION
# ===========================================
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://prosaas.pro/api/gmail/oauth/callback

# 🔑 הוסף כאן / Add here:
ENCRYPTION_KEY=xQz8K9vW2nF5mL7pT3gH1jR6dS4yA8bC0eU9iO5qN2k=
```

---

## ✅ איך לדעת שזה עובד? / How to know it works?

1. **אחרי Restart**, לך לעמוד קבלות / After restart, go to Receipts page
2. לחץ "חיבור Gmail" / Click "Connect Gmail"
3. השלם את תהליך האישור / Complete authorization
4. **אם זה עובד:** תראה "חיבור הצליח" וסינכרון יתחיל
   **If it works:** You'll see "Connection successful" and sync will start
5. **אם לא עובד:** תראה "מפתח ההצפנה לא מוגדר"
   **If not working:** You'll see "Encryption key not configured"

---

## ❓ שגיאות נפוצות / Common Errors

### שגיאה: "encryption_not_configured"
**פתרון / Solution:** ENCRYPTION_KEY חסר או לא תקין / missing or invalid
- וודא שהמפתח ב-.env / Check key in .env
- וודא שהמפתח בפורמט Fernet תקני / Check key is valid Fernet format

### שגיאה: "cryptography package not installed"
**פתרון / Solution:** 
```bash
docker-compose down
docker-compose up -d --build
```

### הקובץ .env לא קיים / .env file doesn't exist
**פתרון / Solution:**
```bash
cp .env.example .env
# ערוך ו הוסף ENCRYPTION_KEY / Edit and add ENCRYPTION_KEY
```

---

## 📚 מידע נוסף / More Information

למדריך מפורט ראה / For detailed guide see:
- `GMAIL_ENCRYPTION_KEY_SETUP.md` - מדריך מלא דו-לשוני / Full bilingual guide
- `FIX_SUMMARY_APPLICATION_ERRORS.md` - סיכום כל התיקונים / Summary of all fixes

---

## 🔒 אבטחה / Security

⚠️ **אל תשתף / Never share:**
- את קובץ ה-.env / The .env file
- את ה-ENCRYPTION_KEY / The ENCRYPTION_KEY
- אל תעלה ל-Git / Don't commit to Git

✅ **שמור בגיבוי מאובטח / Backup securely:**
- שמור את המפתח במקום בטוח / Save key in secure location
- אם תאבד את המפתח, תצטרך לחבר מחדש את Gmail
  If you lose the key, you'll need to reconnect Gmail

---

**סטטוס / Status:** ✅ כל התיקונים הושלמו / All fixes complete
**מוכן לשימוש / Ready to use:** כן / Yes
