# Gmail OAuth Encryption Key Setup Guide
# מדריך הגדרת מפתח הצפנה ל-Gmail OAuth

## English

### What is ENCRYPTION_KEY?
The `ENCRYPTION_KEY` is used to securely encrypt Gmail OAuth refresh tokens before storing them in the database. This ensures that even if someone gains access to your database, they cannot use the stored tokens.

### Where to Add ENCRYPTION_KEY

#### 1. **For Production (Docker Deployment)**

Add the `ENCRYPTION_KEY` to your `.env` file:

```bash
# Location: /path/to/prosaasil/.env

# Gmail OAuth Encryption
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-fernet-encryption-key-here
```

#### 2. **For Docker Compose**

If you're using `docker-compose.yml`, you can either:

**Option A:** Use environment file (recommended)
```yaml
services:
  prosaas-backend:
    env_file:
      - .env
```

**Option B:** Add directly to docker-compose.yml
```yaml
services:
  prosaas-backend:
    environment:
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
```

### How to Generate ENCRYPTION_KEY

**Method 1: Using Python**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Output example:
```
xQz8K9vW2nF5mL7pT3gH1jR6dS4yA8bC0eU9iO5qN2k=
```

**Method 2: Using Docker**
```bash
docker run --rm python:3.11 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Complete Setup Steps

1. **Generate the encryption key:**
   ```bash
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. **Add to your `.env` file:**
   ```bash
   # Copy the generated key and add it to .env
   ENCRYPTION_KEY=xQz8K9vW2nF5mL7pT3gH1jR6dS4yA8bC0eU9iO5qN2k=
   ```

3. **Restart your application:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

4. **Verify the setup:**
   - Go to Gmail Receipts page in your app
   - Click "Connect Gmail"
   - Complete OAuth flow
   - Check that connection succeeds without "encryption_not_configured" error

### Troubleshooting

**Error:** "ENCRYPTION_KEY must be set in production for secure token storage"
- **Solution:** Add `ENCRYPTION_KEY` to your `.env` file and restart the backend service

**Error:** "encryption_not_configured" in OAuth callback
- **Solution:** Generate a valid Fernet key and add it to `.env`

**Error:** "cryptography package not installed"
- **Solution:** Install cryptography package in your Docker image (should be in requirements)

---

## עברית (Hebrew)

### מה זה ENCRYPTION_KEY?
ה-`ENCRYPTION_KEY` משמש להצפנת טוקני OAuth של Gmail לפני שמירתם במסד הנתונים. זה מבטיח שגם אם מישהו יקבל גישה למסד הנתונים שלך, הוא לא יוכל להשתמש בטוקנים השמורים.

### איפה להוסיף את ENCRYPTION_KEY

#### 1. **עבור סביבת ייצור (Docker)**

הוסף את `ENCRYPTION_KEY` לקובץ `.env` שלך:

```bash
# מיקום: /path/to/prosaasil/.env

# הצפנת Gmail OAuth
# ליצור עם: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=המפתח-שיצרת-כאן
```

#### 2. **עבור Docker Compose**

אם אתה משתמש ב-`docker-compose.yml`, אתה יכול:

**אפשרות א': להשתמש בקובץ סביבה (מומלץ)**
```yaml
services:
  prosaas-backend:
    env_file:
      - .env
```

**אפשרות ב': להוסיף ישירות ל-docker-compose.yml**
```yaml
services:
  prosaas-backend:
    environment:
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
```

### איך ליצור ENCRYPTION_KEY

**שיטה 1: באמצעות Python**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

דוגמה לפלט:
```
xQz8K9vW2nF5mL7pT3gH1jR6dS4yA8bC0eU9iO5qN2k=
```

**שיטה 2: באמצעות Docker**
```bash
docker run --rm python:3.11 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### שלבי הגדרה מלאים

1. **ליצור את מפתח ההצפנה:**
   ```bash
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. **להוסיף לקובץ `.env` שלך:**
   ```bash
   # העתק את המפתח שנוצר והוסף אותו ל-.env
   ENCRYPTION_KEY=xQz8K9vW2nF5mL7pT3gH1jR6dS4yA8bC0eU9iO5qN2k=
   ```

3. **להפעיל מחדש את האפליקציה:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

4. **לוודא שההגדרה עובדת:**
   - לעבור לעמוד קבלות Gmail באפליקציה
   - ללחוץ על "חיבור Gmail"
   - להשלים את תהליך ה-OAuth
   - לוודא שהחיבור מצליח ללא שגיאת "encryption_not_configured"

### פתרון בעיות

**שגיאה:** "ENCRYPTION_KEY must be set in production for secure token storage"
- **פתרון:** הוסף `ENCRYPTION_KEY` לקובץ `.env` שלך והפעל מחדש את שירות ה-backend

**שגיאה:** "encryption_not_configured" ב-OAuth callback
- **פתרון:** צור מפתח Fernet תקני והוסף אותו ל-`.env`

**שגיאה:** "cryptography package not installed"
- **פתרון:** התקן את חבילת cryptography בתמונת Docker שלך (אמור להיות ב-requirements)

---

## Security Notes / הערות אבטחה

⚠️ **IMPORTANT / חשוב:**
- Never commit `.env` files to Git / לעולם אל תעלה קבצי `.env` ל-Git
- Keep your `ENCRYPTION_KEY` secret / שמור על `ENCRYPTION_KEY` בסוד
- Use different keys for dev/staging/production / השתמש במפתחות שונים לסביבות שונות
- Backup your `ENCRYPTION_KEY` securely / גבה את `ENCRYPTION_KEY` בצורה מאובטחת
- If you lose the key, you'll need to re-authorize Gmail / אם תאבד את המפתח, תצטרך לאשר מחדש את Gmail

## File Locations / מיקום קבצים

```
prosaasil/
├── .env                          # Add ENCRYPTION_KEY here / הוסף ENCRYPTION_KEY כאן
├── .env.example                  # Template with ENCRYPTION_KEY line / תבנית עם שורת ENCRYPTION_KEY
├── docker-compose.yml            # Docker configuration / הגדרות Docker
└── server/routes_receipts.py    # Code that uses ENCRYPTION_KEY / קוד שמשתמש ב-ENCRYPTION_KEY
```
