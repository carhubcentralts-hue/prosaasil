# Baileys WhatsApp Service

שירות Node.js עצמאי לניהול WhatsApp באמצעות ספריית Baileys למערכת AgentLocator CRM.

## התקנה והפעלה

```bash
# התקנת חבילות
npm install

# הפעלה
npm start

# פיתוח עם hot-reload
npm run dev
```

## API Endpoints

### בדיקת בריאות
- `GET /health` - מצב החיבור ומידע מערכת
- `GET /status` - סטטוס מפורט של החיבור

### אימות
- `GET /qr` - קבלת QR code לסריקה ב-WhatsApp

### שליחת הודעות
- `POST /send` - שליחת הודעת טקסט או מדיה

Example:
```json
{
  "to": "972501234567",
  "type": "text", 
  "text": "שלום מהמערכת!",
  "idempotencyKey": "unique-key-123"
}
```

## אבטחה

- Webhook Secret: משותף עם השרת הראשי לאימות
- Idempotency: מניעת שליחת הודעות כפולות
- Deduplication: מניעת עיבוד הודעות נכנסות כפולות

## סביבת עבודה

```bash
PORT=3001
BAILEYS_WEBHOOK_SECRET=your_shared_secret
PUBLIC_BASE_URL=https://your-server.com
```