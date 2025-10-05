const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');

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

const sessions = new Map(); // tenantId -> { sock, saveCreds, qrDataUrl, connected, starting, pushName }

function authDir(tenantId) {
  // CRITICAL FIX: Unified tenant path (always business_1)
  const normalizedTenant = tenantId === '1' ? 'business_1' : String(tenantId);
  const p = path.join(process.cwd(), 'storage', 'whatsapp', normalizedTenant, 'auth');
  fs.mkdirSync(p, { recursive: true });
  console.log(`[authDir] tenant=${tenantId} -> normalized=${normalizedTenant} -> path=${p}`);
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
  // B3) מניעת מרוצים: אל תריץ start פעמיים
  const tenantId = req.params.tenantId;
  const existing = sessions.get(tenantId);
  if (existing && (existing.sock || existing.starting)) {
    console.log(`[${tenantId}] ⚠️ Already running or starting - skipping duplicate start`);
    return res.json({ok: true}); // כבר רץ
  }
  
  try { 
    await startSession(tenantId); 
    res.json({ ok: true }); 
  }
  catch (e) { 
    console.error('start error', e); 
    res.status(500).json({ error: 'start_failed' }); 
  }
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
  console.log(`[${tenantId}] 🚀 startSession called`);
  const cur = sessions.get(tenantId);
  if (cur?.sock) return cur;
  if (cur?.starting) return cur;
  sessions.set(tenantId, { starting: true });

  const authPath = authDir(tenantId);  // fs.mkdirSync(..., {recursive:true}) כבר קיים
  const { state, saveCreds } = await useMultiFileAuthState(authPath);

  // --- גרסה/דפדפן יציבים (מונע pairing תקוע) ---
  const { version } = await fetchLatestBaileysVersion();
  console.log(`[${tenantId}] 🔧 Using Baileys version:`, version);
  
  const sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false,
    browser: ['AgentLocator', 'Chrome', '10.0'],
    defaultQueryTimeoutMs: 60000,
    connectTimeoutMs: 30000
  });

  const s = { sock, saveCreds, qrDataUrl: '', connected: false, pushName: '', starting: false };
  sessions.set(tenantId, s);
  console.log(`[${tenantId}] 💾 Session stored in memory with stable browser settings`);

  sock.ev.on('creds.update', async () => {
    await saveCreds();
    console.log(`[${tenantId}] 🔐 Credentials saved to disk`);
  });
  sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
    try {
      // DETAILED LOGGING for debugging
      console.log(`[update] ${tenantId}:`, { 
        connection, 
        hasQr: !!qr, 
        reason: lastDisconnect?.error?.output?.statusCode 
      });
      
      // B2) לוגיקת QR יציבה בNode עם qr_code.txt
      const qrFile = path.join(authPath, 'qr_code.txt');
      
      if (qr) {
        s.qrDataUrl = await QRCode.toDataURL(qr);
        console.log(`[${tenantId}] 📱 QR generated successfully`);
        // כתיבת QR לקובץ לפי ההוראות
        try { 
          fs.writeFileSync(qrFile, qr); 
          console.log(`[${tenantId}] 💾 QR saved to ${qrFile}`);
        } catch(e) { 
          console.error(`[${tenantId}] QR file write error:`, e); 
        }
      }
      
      if (connection === 'open') {
        s.connected = true; 
        s.qrDataUrl = '';
        s.pushName = sock?.user?.name || sock?.user?.id || '';
        console.log(`[${tenantId}] ✅ Connected! pushName: ${s.pushName}`);
        // מחיקת QR כשמתחברים לפי ההוראות
        try { 
          if (fs.existsSync(qrFile)) {
            fs.unlinkSync(qrFile); 
            console.log(`[${tenantId}] 🗑️ QR file deleted after connection`);
          }
        } catch(e) { 
          console.error(`[${tenantId}] QR file delete error:`, e); 
        }
      }
      
      if (connection === 'close') {
        s.connected = false;
        const reason = lastDisconnect?.error?.output?.statusCode;
        console.log(`[${tenantId}] ❌ Disconnected. Reason: ${reason}`);
        
        // ✅ FIX: אם קיבלנו loggedOut - קבצי האימות פגומים, צריך לנקות אותם
        if (reason === DisconnectReason.loggedOut) {
          console.log(`[${tenantId}] 🗑️ ${reason} loggedOut - clearing auth files`);
          try {
            const authPath = authDir(tenantId);
            fs.rmSync(authPath, { recursive: true, force: true });
            console.log(`[${tenantId}] ✅ Auth files cleared, will restart with fresh QR`);
            fs.mkdirSync(authPath, { recursive: true });
          } catch (e) {
            console.error(`[${tenantId}] Failed to clear auth files:`, e);
          }
          setTimeout(() => startSession(tenantId), 3000);
          return;
        }
        
        // ✅ FIX: שגיאה restartRequired (515) = Stream Error אחרי pairing מוצלח
        // צריך לנסות מחדש אבל NOT לנקות credentials!
        if (reason === DisconnectReason.restartRequired) {
          console.log(`[${tenantId}] 🔄 515 restartRequired after pairing - will retry with saved credentials`);
          // נקה את ה-socket הישן אבל שמור את ה-credentials
          try {
            if (s.sock) {
              s.sock.removeAllListeners();
              s.sock.end();
            }
          } catch (e) {
            console.log(`[${tenantId}] Socket cleanup warning:`, e.message);
          }
          sessions.delete(tenantId);
          // המתן יותר זמן כדי ש-WhatsApp ייצב
          setTimeout(() => startSession(tenantId), 5000);
          return;
        }
        
        // אם לא loggedOut – ננסה מחדש בעדינות (לא מיד, כדי לא ליצור מרוץ)
        console.log(`[${tenantId}] 🔄 Will retry in 2 seconds...`);
        setTimeout(() => startSession(tenantId), 2000);
      }
    } catch (e) { 
      console.error(`[${tenantId}] [connection.update] error:`, e); 
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
  server = app.listen(PORT, '127.0.0.1', () => {
    const addr = server.address();
    console.error(`[BOOT] Baileys listening on 127.0.0.1:${addr.port} pid=${process.pid} (internal only for security)`);
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