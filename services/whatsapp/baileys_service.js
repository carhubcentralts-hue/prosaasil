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
app.get('/health', (req, res) => res.status(200).send('ok'));  // Add /health alias for Python compatibility
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

app.post('/whatsapp/:tenantId/disconnect', requireSecret, async (req, res) => {
  try { 
    await disconnectSession(req.params.tenantId); 
    return res.json({ ok: true, message: 'Disconnected successfully' }); 
  }
  catch (e) { 
    console.error('[disconnect] error', e); 
    return res.status(500).json({ error: 'disconnect_failed' }); 
  }
});

/** Baileys session logic */
async function startSession(tenantId) {
  console.error(`[${tenantId}] 🚀🚀🚀 DEBUG: startSession called - SHOULD BE VISIBLE!`);
  console.log(`[${tenantId}] 🚀 startSession called`);
  if (sessions.get(tenantId)?.sock) {
    console.log(`[${tenantId}] ⚠️ Session already exists, returning existing`);
    return sessions.get(tenantId);
  }
  console.log(`[${tenantId}] 📁 Loading auth state from: ${authDir(tenantId)}`);
  const { state, saveCreds } = await useMultiFileAuthState(authDir(tenantId));
  console.log(`[${tenantId}] 🔧 Creating WhatsApp socket with iPhone-compatible settings`);
  const sock = makeWASocket({ 
    auth: state, 
    printQRInTerminal: false,
    browser: ['AgentLocator', 'Safari', '15.0'],  // iPhone compatibility
    defaultQueryTimeoutMs: 30000,
    connectTimeoutMs: 15000
  });

  const s = { sock, saveCreds, qrDataUrl: '', connected: false, pushName: '' };
  sessions.set(tenantId, s);
  console.log(`[${tenantId}] 💾 Session stored in memory`);

  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', async (u) => {
    try {
      const { connection, lastDisconnect, qr, isNewLogin } = u;
      console.error(`[${tenantId}] 🚀🚀🚀 CONNECTION UPDATE (ENHANCED DEBUG):`, { 
        connection, 
        hasQr: !!qr, 
        isNewLogin,
        reason: lastDisconnect?.error?.output?.statusCode,
        timestamp: new Date().toISOString(),
        full_update: JSON.stringify(u, null, 2)
      });
      console.log(`[${tenantId}] 🔍 Raw connection update:`, u);
      
      if (qr) {
        console.log(`[${tenantId}] 🔄 Generating iPhone-optimized QR code`);
        // QR optimized for iPhone scanning
        s.qrDataUrl = await QRCode.toDataURL(qr, {
          errorCorrectionLevel: 'H',    // גבוה יותר לiPhone
          type: 'image/png',
          quality: 0.92,
          margin: 2,                    // margin נוח לiPhone
          color: {
            dark: '#000000',
            light: '#FFFFFF'
          },
          width: 512                    // גודל אופטימלי לiPhone
        });
        console.log(`[${tenantId}] ✅ iPhone QR generated, length: ${s.qrDataUrl.length}`);
      }
      
      if (connection === 'open') {
        console.log(`[${tenantId}] ✅ WhatsApp connected successfully`);
        s.connected = true;
        s.pushName = sock?.user?.name || sock?.user?.id || '';
        s.qrDataUrl = '';
        
        // 🚀 Notify Flask about successful connection
        try {
          console.log(`[${tenantId}] 📡 Notifying Flask about connection success`);
          await axios.post(`${FLASK_BASE_URL}/webhook/whatsapp/status`,
            { 
              tenantId, 
              status: 'connected', 
              pushName: s.pushName,
              timestamp: new Date().toISOString()
            },
            { headers: { 'X-Internal-Secret': INTERNAL_SECRET } }
          );
          console.log(`[${tenantId}] ✅ Flask notified about connection`);
        } catch (e) { 
          console.error(`[${tenantId}] ❌ Failed to notify Flask about connection:`, e?.message || e); 
        }
      }
      
      if (connection === 'close') {
        console.log(`[${tenantId}] ❌ WhatsApp connection closed`);
        s.connected = false;
        
        // 🚀 Notify Flask about disconnection
        try {
          console.log(`[${tenantId}] 📡 Notifying Flask about disconnection`);
          await axios.post(`${FLASK_BASE_URL}/webhook/whatsapp/status`,
            { 
              tenantId, 
              status: 'disconnected', 
              reason: lastDisconnect?.error?.output?.statusCode || 'unknown',
              timestamp: new Date().toISOString()
            },
            { headers: { 'X-Internal-Secret': INTERNAL_SECRET } }
          );
          console.log(`[${tenantId}] ✅ Flask notified about disconnection`);
        } catch (e) { 
          console.error(`[${tenantId}] ❌ Failed to notify Flask about disconnection:`, e?.message || e); 
        }
        
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
  console.log(`[${tenantId}] 🔄 resetSession called - full cleanup and restart`);
  const s = sessions.get(tenantId);
  if (s?.sock) {
    try {
      console.log(`[${tenantId}] 🔚 Closing existing socket`);
      s.sock.end();
      s.sock.removeAllListeners();
    } catch (e) {
      console.error(`[${tenantId}] [reset] cleanup error`, e);
    }
  }
  sessions.delete(tenantId);
  
  // Clear auth files
  const authPath = authDir(tenantId);
  try {
    console.log(`[${tenantId}] 🗑️ Clearing auth files from: ${authPath}`);
    await import('fs').then(fs => fs.promises.rm(authPath, { recursive: true, force: true }));
  } catch (e) { console.error(`[${tenantId}] [resetSession] cleanup error`, e); }
  
  console.log(`[${tenantId}] 🆕 Starting fresh session`);
  return await startSession(tenantId);
}

async function disconnectSession(tenantId) {
  console.log(`[${tenantId}] 🔌 disconnectSession called - permanent disconnect`);
  const s = sessions.get(tenantId);
  
  if (s?.sock) {
    try {
      // Send logout command to WhatsApp first
      console.log(`[${tenantId}] 📤 Sending logout to WhatsApp`);
      await s.sock.logout();
    } catch (e) { 
      console.log(`[${tenantId}] ⚠️ Logout command failed (OK if not connected):`, e.message); 
    }
    
    try {
      console.log(`[${tenantId}] 🔚 Closing socket`);
      s.sock.end();
      s.sock.removeAllListeners();
    } catch (e) { 
      console.error(`[${tenantId}] sock.end() failed`, e); 
    }
    
    sessions.delete(tenantId);
  }
  
  // Clear auth files completely
  const authPath = authDir(tenantId);
  try {
    console.log(`[${tenantId}] 🗑️ Removing all auth files from: ${authPath}`);
    await import('fs').then(fs => fs.promises.rm(authPath, { recursive: true, force: true }));
    console.log(`[${tenantId}] ✅ WhatsApp disconnected and cleaned up`);
  } catch (e) { 
    console.error(`[${tenantId}] [disconnectSession] cleanup error`, e); 
  }
  
  return { disconnected: true, message: 'WhatsApp disconnected completely' };
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

// 🚀 Allow direct execution
if (require.main === module) {
  start();
}