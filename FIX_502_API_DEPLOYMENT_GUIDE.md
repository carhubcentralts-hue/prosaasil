# תיקון 502 Bad Gateway על /api - מדריך פריסה

## סיכום התיקון

### הבעיה
- NGINX ניסה להפנות בקשות ל-`backend:5000` שלא היה קיים (רק עם `profiles: [legacy]`)
- בפרודקשן היו שירותים `prosaas-api` ו-`prosaas-calls` רק ב-`docker-compose.prod.yml`
- זה גרם ל-502 Bad Gateway על כל בקשות `/api/`

### הפתרון
1. ✅ הוספנו `prosaas-api` ו-`prosaas-calls` ל-`docker-compose.yml` הבסיסי (לא רק prod)
2. ✅ פישטנו את ה-nginx config לשימוש בשמות שירותים ישירים (`http://prosaas-api:5000`)
3. ✅ הוספנו בדיקת בריאות upstream שמונעת מ-nginx להעלות אם השירותים לא זמינים
4. ✅ עדכנו את worker ו-baileys להיות תלויים ב-prosaas-api

## שינויים שבוצעו

### קבצים שונו:
1. `docker-compose.yml` - הוספת שירותים, עדכון תלויות
2. `docker-compose.prod.yml` - הסרת build args מיותרים
3. `Dockerfile.nginx` - פישוט (ללא envsubst)
4. `docker/nginx/templates/prosaas.conf.template` - שמות שירותים ישירים
5. `docker/nginx/templates/prosaas-ssl.conf.template` - שמות שירותים ישירים
6. `docker/nginx/entrypoint.d/10-check-upstreams.sh` - בדיקת בריאות upstream

### מבנה השירותים החדש:
```
nginx (פורט 80/443)
  ↓
  ├─> prosaas-api:5000 (/api/*)
  ├─> prosaas-calls:5050 (/ws/*, /webhook)
  ├─> frontend:80 (/, /assets)
  └─> n8n:5678 (subdomain)
```

## פריסה

### שלב 1: עדכון הקוד
```bash
git pull origin copilot/fix-502-bad-gateway-api
```

### שלב 2: בניה מחדש של nginx
```bash
docker compose build nginx
```

### שלב 3: הפעלת השירותים
```bash
# סביבת פיתוח
docker compose up -d

# סביבת פרודקשן
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans
```

### שלב 4: בדיקת בריאות
```bash
# בדיקת שירותים פועלים
docker compose ps

# בדיקת לוגים של nginx
docker compose logs nginx --tail=50

# בדיקת upstream health
docker compose exec nginx wget -qO- http://prosaas-api:5000/api/health
docker compose exec nginx wget -qO- http://prosaas-calls:5050/health
```

### שלב 5: וידוא תקינות
```bash
# בדיקה מקומית
curl -i http://localhost/api/auth/csrf
# צריך להחזיר 200

curl -i http://localhost/api/auth/me
# צריך להחזיר 401 או 200 (לא 502!)

# בדיקה בפרודקשן
curl -i https://prosaas.pro/api/auth/csrf
# צריך להחזיר 200

curl -i https://prosaas.pro/api/auth/me
# צריך להחזיר 401 או 200 (לא 502!)
```

## Acceptance Criteria ✅

אחרי הפריסה, הבדיקות הבאות חייבות לעבור:

1. ✅ `curl https://prosaas.pro/api/auth/csrf` → **200 OK**
2. ✅ `curl https://prosaas.pro/api/auth/me` → **401/200** (לא 502)
3. ✅ `docker compose ps` → כל השירותים במצב **healthy**
4. ✅ אין שגיאות 502 בלוגים של nginx

## פתרון בעיות

### אם עדיין יש 502:
```bash
# בדיקה אם השירותים רצים
docker compose ps | grep prosaas

# בדיקה אם nginx רואה את השירותים
docker compose exec nginx ping -c 1 prosaas-api
docker compose exec nginx wget -qO- http://prosaas-api:5000/api/health

# בדיקת לוגים
docker compose logs prosaas-api --tail=50
docker compose logs nginx --tail=50
```

### אם nginx לא עולה:
```bash
# בדיקה אם יש בעיית upstream
docker compose logs nginx | grep "upstream"

# עצירה ובנייה מחדש
docker compose down
docker compose build --no-cache nginx
docker compose up -d
```

### אם יש orphan containers:
```bash
docker compose down --remove-orphans
docker compose up -d
```

## הערות חשובות

1. **שמות שירותים קבועים**: nginx עכשיו מצביע ישירות ל-`prosaas-api:5000` ו-`prosaas-calls:5050`
2. **אין יותר profiles**: השירותים עולים תמיד (לא צריך `--profile`)
3. **אין יותר envsubst**: הקונפיגורציה פשוטה ובלי "קסמים"
4. **בדיקת בריאות**: nginx לא יעלה אם השירותים לא זמינים (fail-fast)

## רולבק במקרה חירום

אם משהו לא עובד:
```bash
# חזרה לגרסה הקודמת
git checkout main
docker compose down
docker compose build nginx
docker compose up -d
```
