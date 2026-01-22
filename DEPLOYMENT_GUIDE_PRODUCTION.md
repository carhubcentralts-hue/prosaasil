# מדריך פריסת פרודקשן - ProSaaS

## 🎯 מטרה

סקריפט פריסה אחד (`scripts/dcprod.sh`) שהוא:
- **מקור אמת יחיד** לפריסה בפרודקשן
- **לא יוצר סטאקים כפולים** (prosaas-* vs prosaasil-*)
- **לא גורם ל-port conflicts** (רק nginx על 80/443)
- **עובד אותו דבר תמיד** (CI / ידני / שחזור)
- **Idempotent** - אפשר להריץ 100 פעמים בלי לשבור כלום

## ✅ עקרונות חובה

1. **רק docker compose** – לא docker run
2. **בלי -p (project name)** – Docker קובע שם לפי תיקייה → אותו סטאק תמיד
3. **תמיד טוען שני קבצים:**
   - `docker-compose.yml` (base)
   - `docker-compose.prod.yml` (production overrides)
4. **לא מפרסם ports לשירותים פנימיים** – רק nginx עם 80/443
5. **Idempotent** – בטוח להריץ מספר פעמים

## 🚀 שימוש נכון

### פריסה מלאה (נקי)

```bash
# שלב 1: הורדה נקייה של כל הסטאק
./scripts/dcprod.sh down

# שלב 2: פריסה עם build מחדש
./scripts/dcprod.sh up -d --build --force-recreate

# שלב 3: בדיקות
./scripts/verify_production.sh
```

### עדכון (ללא rebuild)

```bash
# משוך שינויים וסתם תפעיל מחדש
./scripts/dcprod.sh up -d
```

### עדכון עם rebuild מלא

```bash
# build מחדש ללא cache
./scripts/dcprod.sh build --no-cache

# הפעל מחדש
./scripts/dcprod.sh up -d --force-recreate
```

### ניהול ובדיקות

```bash
# בדיקת סטטוס
./scripts/dcprod.sh ps

# לוגים של שירות מסוים
./scripts/dcprod.sh logs -f prosaas-api

# לוגים של כל השירותים (30 שורות אחרונות)
./scripts/dcprod.sh logs --tail=30

# הרצת פקודה בתוך קונטיינר
./scripts/dcprod.sh exec prosaas-api python -c "print('hello')"

# כיבוי מסודר
./scripts/dcprod.sh down

# כיבוי עם מחיקת volumes (⚠️ זהירות!)
./scripts/dcprod.sh down -v
```

## 🧪 תהליך פריסה מומלץ

### פריסה ראשונית (clean slate)

```bash
# 1. עצירה ומחיקה של סטאקים קודמים (חד-פעמי!)
docker compose down --remove-orphans
docker stop $(docker ps -q) || true
docker rm $(docker ps -aq) || true

# 2. וודא שרשת קיימת
docker network ls | grep prosaas-net || docker network create prosaas-net

# 3. פריסה
cd /path/to/prosaasil
./scripts/dcprod.sh up -d --build

# 4. בדיקה
./scripts/verify_production.sh
```

### פריסה עדכון (update deployment)

```bash
# 1. משוך שינויים
git pull origin main

# 2. בנה מחדש
./scripts/dcprod.sh build --no-cache

# 3. הפעל מחדש
./scripts/dcprod.sh up -d --force-recreate

# 4. בדיקה
./scripts/verify_production.sh
```

### פריסה מהירה (hotfix)

```bash
# 1. משוך שינויים
git pull origin main

# 2. הפעל מחדש (ללא build)
./scripts/dcprod.sh up -d

# 3. אם צריך restart לשירות מסוים
./scripts/dcprod.sh restart prosaas-api
```

## 📋 בדיקות חובה אחרי פריסה

```bash
# 1. כל הקונטיינרים רצים
./scripts/dcprod.sh ps

# תוצאה צפויה:
# - nginx → Up + healthy
# - prosaas-api → Up + healthy  
# - prosaas-calls → Up + healthy
# - frontend → Up + healthy
# - redis → Up
# - baileys → Up + healthy
# - worker → Up + healthy
# - n8n → Up
# - אין Restart loops

# 2. nginx עונה
curl -I http://localhost/health
# תוצאה צפויה: 200 OK

# 3. הרצת בדיקות מלאות
./scripts/verify_production.sh
```

## 🏗️ ארכיטקטורה - מה רץ איפה

### פורטים (מי חשוף החוצה)

| שירות | פורט פנימי | פורט חיצוני | גישה |
|-------|-----------|-------------|------|
| nginx | 80, 443 | 80, 443 | ציבורי (Host + Internet) |
| prosaas-api | 5000 | - | פנימי (רשת Docker בלבד) |
| prosaas-calls | 5050 | - | פנימי (רשת Docker בלבד) |
| frontend | 80 | - | פנימי (רשת Docker בלבד) |
| redis | 6379 | - | פנימי (רשת Docker בלבד) |
| baileys | 3300 | - | פנימי (רשת Docker בלבד) |
| n8n | 5678 | - | פנימי (רשת Docker בלבד) |
| worker | - | - | פנימי (רשת Docker בלבד) |

### זרימת תעבורה

```
אינטרנט / Cloudflare
         ↓
    nginx:80/443 (חשיפת Host)
         ↓
    prosaas-net (רשת Docker)
         ↓
    ┌──────────────────────────────────┐
    │                                  │
    ├→ prosaas-api:5000               │
    ├→ prosaas-calls:5050             │
    ├→ frontend:80                    │
    ├→ n8n:5678                       │
    ├→ baileys:3300 ← prosaas-api    │
    ├→ redis:6379 ← כל השירותים       │
    └──────────────────────────────────┘
```

## 🚫 דברים שאסור לעשות

### ❌ אל תשתמש ב-project name

```bash
# ❌ לא נכון
docker compose -f docker-compose.yml -f docker-compose.prod.yml -p prosaas up -d

# ✅ נכון (דרך הסקריפט)
./scripts/dcprod.sh up -d
```

### ❌ אל תשתמש ב-docker run

```bash
# ❌ לא נכון
docker run -d --name redis redis:7-alpine

# ✅ נכון - רק דרך docker-compose
./scripts/dcprod.sh up -d redis
```

### ❌ אל תחשוף פורטים של שירותים פנימיים

```yaml
# ❌ לא נכון בפרודקשן
redis:
  ports:
    - "6379:6379"

# ✅ נכון
redis:
  expose:
    - "6379"
```

### ❌ אל תשתמש ב-localhost בתוך nginx

```nginx
# ❌ לא נכון
proxy_pass http://localhost:5000;

# ✅ נכון
proxy_pass http://prosaas-api:5000;
```

## 🔧 פתרון בעיות נפוצות

### בעיה: "port already in use"

```bash
# פתרון: מצא מה משתמש בפורט
sudo netstat -tulpn | grep :6379

# עצור את כל הקונטיינרים
docker stop $(docker ps -q) || true

# פריסה מחדש
./scripts/dcprod.sh up -d
```

### בעיה: סטאקים כפולים (prosaas-* ו-prosaasil-*)

```bash
# פתרון: מחק הכל והתחל מחדש
docker compose down --remove-orphans
docker ps -a  # ודא שאין קונטיינרים

# פריסה מחדש
./scripts/dcprod.sh up -d
```

### בעיה: nginx לא מוצא upstreams

```bash
# בדיקה: nginx יכול לפנות לשירותים
docker exec -it $(docker ps -q -f name=nginx) nslookup prosaas-api
docker exec -it $(docker ps -q -f name=nginx) nslookup redis

# אם לא עובד - ודא שכולם על אותה רשת
./scripts/dcprod.sh ps
docker inspect prosaas-api | grep -A 10 Networks
```

### בעיה: 521 מ-Cloudflare

```bash
# בדיקה: nginx חי
curl -I http://localhost/health

# בדיקה: nginx יכול להגיע ל-API
docker exec -it $(docker ps -q -f name=nginx) curl -I http://prosaas-api:5000/health

# לוגים
./scripts/dcprod.sh logs --tail=100 nginx
./scripts/dcprod.sh logs --tail=100 prosaas-api
```

## 🧠 למה זה פותר את הבעיות

### לפני (עם -p prosaas)

```bash
# התיקייה: prosaasil
# הפקודה: docker compose -p prosaas up

Docker יוצר:
- prosaas-redis
- prosaas-nginx
- prosaas-api

# פריסה נוספת באותו שרת:
Docker מנסה ליצור שוב:
- prosaas-redis ← קונפליקט!
- prosaas-nginx ← קונפליקט!
```

### אחרי (בלי -p)

```bash
# התיקייה: prosaasil
# הפקודה: docker compose up

Docker יוצר:
- prosaasil-redis
- prosaasil-nginx
- prosaasil-api

# פריסה נוספת - רק מעדכן את אותם קונטיינרים
# אין יצירת כפילויות!
```

## 📝 סיכום

### מה זה נותן לך

✅ **אין יותר סטאקים כפולים** – Docker קובע שם לפי תיקייה
✅ **אין port conflicts** – רק nginx חשוף החוצה
✅ **nginx תמיד רואה שירותים** – דרך שמות שירותים ברשת Docker
✅ **אין 521** – בגלל startup order / DNS מסודר
✅ **Idempotent** – בטוח להריץ מספר פעמים
✅ **מקור אמת יחיד** – כל פריסה עוברת דרך אותו סקריפט

### זרימת עבודה מומלצת

```bash
# 1. Development: עבוד על feature branch
git checkout -b feature/my-feature

# 2. Test: בדוק מקומית
docker compose up -d  # dev mode

# 3. Deploy to staging/production:
git checkout main
git pull
./scripts/dcprod.sh up -d --build
./scripts/verify_production.sh

# 4. Monitor:
./scripts/dcprod.sh logs -f
```

### אחרי הפריסה

אם יש תקלות:
- ✅ לא בגלל Docker compose
- ✅ לא בגלל port conflicts
- ✅ לא בגלל סטאקים כפולים
- 🔍 רק בגלל: קוד, nginx config, או env vars

## 🔒 אבטחה

- רק nginx חשוף לאינטרנט
- כל השירותים הפנימיים מוגנים ברשת Docker
- אין חשיפת פורטים מיותרת
- Redis, Baileys, API - רק פנימי

---

**נוצר:** 2026-01-22  
**גרסה:** 1.0  
**מטרה:** מקור אמת יחיד לפריסת פרודקשן
