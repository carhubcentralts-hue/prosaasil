const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const axios = require('axios');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.BAILEYS_PORT || 3300;
const INTERNAL_SECRET = process.env.INTERNAL_SECRET;
const FLASK_BASE_URL = process.env.FLASK_BASE_URL || 'http://127.0.0.1:5000';
if (!INTERNAL_SECRET) { console.error('INTERNAL_SECRET missing'); process.exit(1); }

const sessions = new Map(); // tenantId -> { sock, saveCreds, qrDataUrl, connected, pushName }

function authDir(tenantId) {
  const p = path.join(process.cwd(), 'storage', 'whatsapp', String(tenantId), 'auth');
  fs.mkdirSync(p, { recursive: true });      // ← מונע EACCES/ENOENT
  return p;
}

async function startSession(tenantId) {
  if (sessions.get(tenantId)?.sock) return sessions.get(tenantId);

  const { state, saveCreds } = await useMultiFileAuthState(authDir(tenantId));
  const sock = makeWASocket({ auth: state, printQRInTerminal: false });
  const s = { sock, saveCreds, qrDataUrl: '', connected: false, pushName: '' };
  sessions.set(tenantId, s);

  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', async (u) => {
    try {
      const { connection, lastDisconnect, qr } = u;
      if (qr) s.qrDataUrl = await QRCode.toDataURL(qr);
      if (connection === 'open') {
        s.connected = true;
        s.pushName = sock?.user?.name || sock?.user?.id || '';
        s.qrDataUrl = '';
      }
      if (connection === 'close') {
        s.connected = false;
        const shouldReconnect = (lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut);
        if (shouldReconnect) setTimeout(() => startSession(tenantId), 2000);
      }
    } catch (e) { console.error('[connection.update] error', e); }
  });

  // העברת הודעות ל-Flask (לא מפיל תהליך אם נכשל)
  sock.ev.on('messages.upsert', async (payload) => {
    try {
      await axios.post(`${FLASK_BASE_URL}/webhook/whatsapp/incoming`,
        { tenantId, payload },
        { headers: { 'X-Internal-Secret': INTERNAL_SECRET } }
      );
    } catch (e) { console.error('[Webhook→Flask] failed', e?.message || e); }
  });

  return s;
}

function requireSecret(req, res, next) {
  if (req.header('X-Internal-Secret') !== INTERNAL_SECRET)
    return res.status(401).json({ error: 'unauthorized' });
  next();
}

app.get('/healthz', (req, res) => res.status(200).send('ok'));

app.post('/whatsapp/:tenantId/start', requireSecret, async (req, res) => {
  try { await startSession(req.params.tenantId); res.json({ ok: true }); }
  catch (e) { console.error('start error', e); res.status(500).json({ error: 'start_failed' }); }
});

app.get('/whatsapp/:tenantId/status', requireSecret, (req, res) => {
  const s = sessions.get(req.params.tenantId);
  res.json({ connected: !!s?.connected, pushName: s?.pushName || '', hasQR: !!s?.qrDataUrl });
});

app.get('/whatsapp/:tenantId/qr', requireSecret, (req, res) => {
  const s = sessions.get(req.params.tenantId);
  if (s?.qrDataUrl) return res.json({ dataUrl: s.qrDataUrl }); // תמיד JSON תקין
  return res.status(404).json({ error: 'no_qr' });             // לא 200 ריק
});

// לא למות בשקט:
process.on('unhandledRejection', err => console.error('[UNHANDLED]', err));
process.on('uncaughtException', err => console.error('[UNCAUGHT]', err));

app.listen(PORT, '127.0.0.1', () => console.log(`Baileys service on ${PORT}`));
setInterval(() => console.log('💓 baileys alive'), 30000);