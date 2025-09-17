const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');

const PORT = Number(process.env.BAILEYS_PORT || 3300);
const INTERNAL_SECRET = process.env.INTERNAL_SECRET;
const FLASK_BASE_URL = process.env.FLASK_BASE_URL || 'http://127.0.0.1:5000';

if (!INTERNAL_SECRET) {
  console.error('[FATAL] INTERNAL_SECRET missing');
  process.exit(1);
}

const app = express();
app.use(cors());
app.use(express.json());

/** simple health BEFORE anything else */
app.get('/healthz', (req, res) => res.status(200).send('ok'));
app.get('/', (req, res) => res.status(200).send('ok'));

const sessions = new Map(); // tenantId -> { sock, saveCreds, qrDataUrl, connected, pushName }

function authDir(tenantId) {
  const p = path.join(process.cwd(), 'storage', 'whatsapp', String(tenantId), 'auth');
  fs.mkdirSync(p, { recursive: true });
  return p;
}
function requireSecret(req, res, next) {
  if (req.header('X-Internal-Secret') !== INTERNAL_SECRET) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  next();
}

/** REST API (always the same app instance) */
app.post('/whatsapp/:tenantId/start', requireSecret, async (req, res) => {
  try { await startSession(req.params.tenantId); return res.json({ ok: true }); }
  catch (e) { console.error('[start] error', e); return res.status(500).json({ error: 'start_failed' }); }
});
app.get('/whatsapp/:tenantId/status', requireSecret, (req, res) => {
  const s = sessions.get(req.params.tenantId);
  return res.json({ connected: !!s?.connected, pushName: s?.pushName || '', hasQR: !!s?.qrDataUrl });
});
app.get('/whatsapp/:tenantId/qr', requireSecret, (req, res) => {
  const s = sessions.get(req.params.tenantId);
  if (s?.qrDataUrl) return res.json({ dataUrl: s.qrDataUrl });
  return res.status(404).json({ error: 'no_qr' });
});
app.post('/whatsapp/:tenantId/reset', requireSecret, async (req, res) => {
  try { 
    await resetSession(req.params.tenantId); 
    return res.json({ ok: true }); 
  }
  catch (e) { 
    console.error('[reset] error', e); 
    return res.status(500).json({ error: 'reset_failed' }); 
  }
});

/** Baileys session logic */
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
      console.log(`[${tenantId}] Connection update:`, { connection, qr: !!qr, lastDisconnect: lastDisconnect?.error?.output?.statusCode });
      
      if (qr) {
        console.log(`[${tenantId}] 🔄 Generating new QR code`);
        s.qrDataUrl = await QRCode.toDataURL(qr);
      }
      
      if (connection === 'open') {
        console.log(`[${tenantId}] ✅ WhatsApp connected successfully`);
        s.connected = true;
        s.pushName = sock?.user?.name || sock?.user?.id || '';
        s.qrDataUrl = '';
      }
      
      if (connection === 'close') {
        console.log(`[${tenantId}] ❌ WhatsApp connection closed`);
        s.connected = false;
        const shouldReconnect =
          (lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut);
        if (shouldReconnect) {
          console.log(`[${tenantId}] 🔄 Will reconnect in 2 seconds`);
          setTimeout(() => startSession(tenantId), 2000);
        } else {
          console.log(`[${tenantId}] ⚠️ Logged out - won't reconnect`);
        }
      }
      
      if (connection === 'connecting') {
        console.log(`[${tenantId}] 🔗 Connecting to WhatsApp...`);
      }
      
    } catch (e) { 
      console.error(`[${tenantId}] [connection.update] Error:`, e); 
    }
  });

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

async function resetSession(tenantId) {
  const s = sessions.get(tenantId);
  if (s?.sock) {
    try {
      s.sock.end();
      s.sock.removeAllListeners();
    } catch (e) {
      console.error('[reset] cleanup error', e);
    }
  }
  sessions.delete(tenantId);
  return await startSession(tenantId);
}

/** single server instance – we export start() to avoid double listen */
let server = null;
function start() {
  if (server) return server;
  server = app.listen(PORT, '0.0.0.0', () => {
    const addr = server.address();
    console.error(`[BOOT] Baileys listening on ${addr.address}:${addr.port} pid=${process.pid}`);
  });
  server.on('error', (err) => { console.error('[SERVER ERROR]', err); });
  process.on('unhandledRejection', (err) => console.error('[UNHANDLED]', err));
  process.on('uncaughtException', (err) => console.error('[UNCAUGHT]', err));
  return server;
}

module.exports = { start, app };