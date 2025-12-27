const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const axios = require('axios');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');

// ⚡ PERFORMANCE: Connection pooling with keep-alive
const keepAliveAgent = new http.Agent({ 
  keepAlive: true, 
  maxSockets: 100,
  timeout: 30000  // 🔧 Increased from 10s to 30s for WhatsApp operations
});

// ⚡ PERFORMANCE: Configure axios globally with keep-alive
axios.defaults.httpAgent = keepAliveAgent;
axios.defaults.timeout = 30000;  // 🔧 Increased from 10s to 30s for Flask webhooks

const PORT = Number(process.env.BAILEYS_PORT || 3300);
const HOST = process.env.BAILEYS_HOST || '0.0.0.0';  // ✅ Listen on all interfaces for Docker networking
const INTERNAL_SECRET = process.env.INTERNAL_SECRET;
const FLASK_BASE_URL = process.env.FLASK_BASE_URL || 'http://127.0.0.1:5000';

if (!INTERNAL_SECRET) {
  console.error('[FATAL] INTERNAL_SECRET missing');
  process.exit(1);
}

/**
 * 🔔 BUILD 151: Notify backend about WhatsApp connection status changes
 * This creates/clears notifications for business owners when WhatsApp disconnects/reconnects
 */
async function notifyBackendWhatsappStatus(tenantId, status, reason = null) {
  try {
    console.log(`[${tenantId}] 🔔 Notifying backend: WhatsApp ${status}${reason ? ` (reason: ${reason})` : ''}`);
    
    await axios.post(`${FLASK_BASE_URL}/api/internal/whatsapp/status-webhook`,
      { tenant_id: tenantId, status, reason },
      { 
        headers: { 
          'Content-Type': 'application/json',
          'X-Internal-Secret': INTERNAL_SECRET 
        },
        timeout: 5000
      }
    );
    console.log(`[${tenantId}] ✅ Backend notified successfully about ${status}`);
  } catch (err) {
    console.error(`[${tenantId}] ⚠️ Failed to notify backend about WhatsApp status:`, err?.message || err);
  }
}

const app = express();
app.use(cors());
app.use(express.json());

/** simple health BEFORE anything else */
app.get('/healthz', (req, res) => res.status(200).send('ok'));
app.get('/health', (req, res) => res.status(200).send('ok'));  // Add /health alias for Python compatibility
app.get('/', (req, res) => res.status(200).send('ok'));

const sessions = new Map(); // tenantId -> { sock, saveCreds, qrDataUrl, connected, starting, pushName, reconnectAttempts }

// 🔧 HARDENING 1.1: Exponential backoff configuration for reconnection
// 🔥 FIX: Increased resilience for slow/unstable connections
const RECONNECT_CONFIG = {
  baseDelay: 5000,    // 5 seconds
  maxDelay: 120000,   // 🔧 Increased from 60s to 120s (2 minutes max)
  multiplier: 1.5,    // 🔧 Reduced from 2 to 1.5 for gentler backoff
  maxAttempts: 20     // 🔧 Increased from 10 to 20 attempts - don't give up easily!
};

function getReconnectDelay(attempts) {
  const delay = Math.min(
    RECONNECT_CONFIG.baseDelay * Math.pow(RECONNECT_CONFIG.multiplier, attempts),
    RECONNECT_CONFIG.maxDelay
  );
  return delay;
}

function authDir(tenantId) {
  // 🔧 HARDENING 1.2: Multi-tenant support - NO hardcoded business_1
  // tenantId should already be in format "business_X" from Python
  const normalizedTenant = tenantId.startsWith('business_') ? tenantId : `business_${tenantId}`;
  const p = path.join(process.cwd(), 'storage', 'whatsapp', normalizedTenant, 'auth');
  fs.mkdirSync(p, { recursive: true });
  console.log(`[WA] authDir: tenant=${tenantId} -> path=${p}`);
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
  const hasSession = !!s;
  const hasSocket = !!s?.sock;
  const isConnected = !!s?.connected;
  const hasQR = !!s?.qrDataUrl;
  const reconnectAttempts = s?.reconnectAttempts || 0;
  
  // 🔧 ENHANCED: Return detailed diagnostic info
  const diagnostics = {
    connected: isConnected,
    pushName: s?.pushName || '',
    hasQR: hasQR,
    hasSession,
    hasSocket,
    reconnectAttempts,
    sessionState: hasSession ? (isConnected ? 'connected' : (hasQR ? 'waiting_qr' : 'connecting')) : 'not_started',
    timestamp: new Date().toISOString()
  };
  
  console.log(`[WA] Status check for ${req.params.tenantId}:`, diagnostics);
  return res.json(diagnostics);
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

// 🔧 NEW: Comprehensive diagnostics endpoint for troubleshooting
app.get('/whatsapp/:tenantId/diagnostics', requireSecret, (req, res) => {
  const tenantId = req.params.tenantId;
  const s = sessions.get(tenantId);
  const authPath = authDir(tenantId);
  const qrFile = path.join(authPath, 'qr_code.txt');
  const credsFile = path.join(authPath, 'creds.json');
  
  const diagnostics = {
    tenant_id: tenantId,
    timestamp: new Date().toISOString(),
    session: {
      exists: !!s,
      connected: !!s?.connected,
      has_socket: !!s?.sock,
      has_qr_data: !!s?.qrDataUrl,
      starting: !!s?.starting,
      push_name: s?.pushName || null,
      reconnect_attempts: s?.reconnectAttempts || 0
    },
    filesystem: {
      auth_path: authPath,
      auth_path_exists: fs.existsSync(authPath),
      qr_file_exists: fs.existsSync(qrFile),
      creds_file_exists: fs.existsSync(credsFile)
    },
    config: {
      max_reconnect_attempts: RECONNECT_CONFIG.maxAttempts,
      base_delay_ms: RECONNECT_CONFIG.baseDelay,
      max_delay_ms: RECONNECT_CONFIG.maxDelay,
      connect_timeout_ms: 30000,
      query_timeout_ms: 20000
    },
    server: {
      port: PORT,
      host: HOST,
      total_sessions: sessions.size,
      uptime_seconds: Math.floor(process.uptime())
    }
  };
  
  console.log(`[WA] Diagnostics requested for ${tenantId}:`, JSON.stringify(diagnostics, null, 2));
  return res.json(diagnostics);
});

// ⚡ FAST typing indicator endpoint - MULTI-TENANT SUPPORT
app.post('/sendTyping', async (req, res) => {
  try {
    const { jid, typing = true, tenantId } = req.body;
    
    if (!jid) {
      return res.status(400).json({ error: 'Missing jid' });
    }
    
    // 🔧 HARDENING 1.2: tenantId is REQUIRED - no fallback
    if (!tenantId) {
      console.error('[WA-ERROR] sendTyping: Missing tenantId');
      return res.status(400).json({ error: 'Missing tenantId' });
    }
    
    const s = sessions.get(tenantId);
    
    if (!s || !s.sock || !s.connected) {
      return res.status(503).json({ error: 'WhatsApp not connected' });
    }
    
    // Send typing indicator (fire and forget - don't wait)
    s.sock.sendPresenceUpdate(typing ? 'composing' : 'paused', jid).catch(() => {});
    
    return res.json({ ok: true });
  } catch (e) {
    return res.status(500).json({ error: 'typing_failed' });
  }
});

app.post('/send', async (req, res) => {
  const startTime = Date.now();
  try {
    const { to, text, type = 'text', tenantId } = req.body;
    
    if (!to || !text) {
      return res.status(400).json({ error: 'Missing required fields: to, text' });
    }
    
    // 🔧 HARDENING 1.2: tenantId is REQUIRED - no fallback
    if (!tenantId) {
      console.error('[WA-ERROR] /send: Missing tenantId');
      return res.status(400).json({ error: 'Missing tenantId' });
    }
    
    const s = sessions.get(tenantId);
    
    if (!s || !s.sock || !s.connected) {
      console.error(`[WA-ERROR] WhatsApp not connected for ${tenantId}`);
      return res.status(503).json({ error: 'WhatsApp not connected' });
    }
    
    console.log(`[send] ⚡ Sending to ${to.substring(0, 15)}...`);
    
    // 🔥 FIX: Remove timeout - let Baileys finish sending!
    // The 10s timeout was causing phantom sends because the Promise.race
    // would reject early but sock.sendMessage kept running in background
    const result = await s.sock.sendMessage(to, { text: text });
    
    const duration = Date.now() - startTime;
    console.log(`[send] ✅ Message sent in ${duration}ms, messageId: ${result.key.id}`);
    
    return res.json({ 
      ok: true, 
      messageId: result.key.id,
      status: 'sent',
      duration_ms: duration
    });
    
  } catch (e) {
    const duration = Date.now() - startTime;
    console.error(`[send] ❌ Failed after ${duration}ms:`, e.message);
    return res.status(500).json({ 
      error: 'send_failed', 
      message: e.message,
      duration_ms: duration
    });
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
  
  // ⚡ OPTIMIZED Baileys socket for maximum speed & reliability
  const sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false,
    browser: ['AgentLocator', 'Chrome', '10.0'],
    markOnlineOnConnect: false,  // ⚡ Don't mark online - saves bandwidth
    syncFullHistory: false,  // ⚡ Don't sync history - CRITICAL for speed
    shouldSyncHistoryMessage: false,  // ⚡ No message history sync
    getMessage: async () => undefined,  // ⚡ Don't fetch old messages - saves time
    defaultQueryTimeoutMs: 20000,  // 🔧 Increased from 7s to 20s for slow connections
    connectTimeoutMs: 30000,  // 🔧 Increased from 7s to 30s for reliable connection
    retryRequestDelayMs: 500,  // 🔧 Added: Delay between retry attempts
    maxMsgRetryCount: 5,  // 🔧 Added: Max retries for failed messages
    keepAliveIntervalMs: 30000  // 🔧 Added: Keep connection alive
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
      const reason = lastDisconnect?.error?.output?.statusCode;
      const reasonMessage = lastDisconnect?.error?.message || String(reason || '');
      
      // 🔧 ENHANCED: More detailed logging for connection diagnostics
      const timestamp = new Date().toISOString();
      console.log(`[WA] ${timestamp} connection update: tenant=${tenantId}, state=${connection || 'none'}, reason=${reason || 'none'}, reasonMsg=${reasonMessage || 'none'}, hasQR=${!!qr}`);
      
      // B2) לוגיקת QR יציבה בNode עם qr_code.txt
      const qrFile = path.join(authPath, 'qr_code.txt');
      
      if (qr) {
        // 🔧 ENHANCED: Add QR generation timing
        const qrStartTime = Date.now();
        s.qrDataUrl = await QRCode.toDataURL(qr);
        const qrDuration = Date.now() - qrStartTime;
        console.log(`[WA] ${tenantId}: ✅ QR generated successfully in ${qrDuration}ms`);
        console.log(`[WA] ${tenantId}: QR length=${qr.length}, dataUrl length=${s.qrDataUrl.length}`);
        
        try { 
          fs.writeFileSync(qrFile, qr);
          console.log(`[WA] ${tenantId}: QR saved to file: ${qrFile}`);
        } catch(e) { 
          console.error(`[WA-ERROR] ${tenantId}: QR file write error:`, e); 
        }
      }
      
      if (connection === 'open') {
        s.connected = true; 
        s.qrDataUrl = '';
        s.pushName = sock?.user?.name || sock?.user?.id || '';
        s.reconnectAttempts = 0;  // 🔧 HARDENING 1.1: Reset reconnect counter on success
        const phoneNumber = sock?.user?.id || 'unknown';
        console.log(`[WA] ${tenantId}: ✅ Connected! pushName=${s.pushName}, phone=${phoneNumber}`);
        console.log(`[WA] ${tenantId}: Session info - id=${sock?.user?.id}, name=${sock?.user?.name}`);
        
        // מחיקת QR כשמתחברים
        try { 
          if (fs.existsSync(qrFile)) {
            fs.unlinkSync(qrFile);
            console.log(`[WA] ${tenantId}: QR file deleted after connection`);
          }
        } catch(e) { 
          console.error(`[WA-ERROR] ${tenantId}: QR file delete error:`, e); 
        }
        
        // 🔔 BUILD 151: Notify backend that WhatsApp is connected
        notifyBackendWhatsappStatus(tenantId, 'connected', null);
      }
      
      if (connection === 'close') {
        s.connected = false;
        console.log(`[WA] ${tenantId}: ❌ Disconnected. reason=${reason}, message=${reasonMessage}`);
        console.log(`[WA] ${tenantId}: Disconnect details - reasonCode=${reason}, lastError=${JSON.stringify(lastDisconnect?.error || {})}`);
        
        // 🔥 CRITICAL: Always clean up socket before reconnect
        try {
          if (s.sock) {
            s.sock.removeAllListeners();
            s.sock.end();
          }
        } catch (e) {
          console.log(`[WA] ${tenantId}: Socket cleanup warning: ${e.message}`);
        }
        
        // CASE 1: Logged out - clear everything and notify backend
        if (reason === DisconnectReason.loggedOut) {
          console.log(`[WA] ${tenantId}: 🔴 LOGGED_OUT - User logged out on phone, clearing auth files`);
          
          // 🔔 BUILD 151: Notify backend about permanent disconnect
          notifyBackendWhatsappStatus(tenantId, 'disconnected', 'logged_out');
          
          try {
            const authPath = authDir(tenantId);
            fs.rmSync(authPath, { recursive: true, force: true });
            console.log(`[WA] ${tenantId}: Auth files cleared, will restart with fresh QR`);
            fs.mkdirSync(authPath, { recursive: true });
          } catch (e) {
            console.error(`[WA-ERROR] ${tenantId}: Failed to clear auth files:`, e);
          }
          sessions.delete(tenantId);
          console.log(`[WA] ${tenantId}: Will restart session in 5 seconds...`);
          setTimeout(() => startSession(tenantId), 5000);
          return;
        }
        
        // CASE 2: restartRequired (515) - keep credentials, just restart
        if (reason === DisconnectReason.restartRequired) {
          console.log(`[WA] ${tenantId}: 🔄 RESTART_REQUIRED (515) - WhatsApp server requested restart`);
          sessions.delete(tenantId);
          console.log(`[WA] ${tenantId}: Will retry connection in 5 seconds...`);
          setTimeout(() => startSession(tenantId), 5000);
          return;
        }
        
        // CASE 3: Other disconnects - use exponential backoff
        // 🔧 HARDENING 1.1: Exponential backoff reconnection
        const attempts = (s.reconnectAttempts || 0) + 1;
        
        if (attempts > RECONNECT_CONFIG.maxAttempts) {
          console.error(`[WA-ERROR] ${tenantId}: 🔴 Max reconnect attempts (${RECONNECT_CONFIG.maxAttempts}) reached`);
          console.error(`[WA-ERROR] ${tenantId}: Giving up after ${attempts} attempts. Manual intervention required.`);
          // 🔔 Notify backend about repeated failure
          notifyBackendWhatsappStatus(tenantId, 'disconnected', 'max_attempts_exceeded');
          sessions.delete(tenantId);
          return;
        }
        
        const delay = getReconnectDelay(attempts - 1);
        console.log(`[WA] ${tenantId}: 🔄 Auto-reconnecting in ${delay/1000}s (attempt ${attempts}/${RECONNECT_CONFIG.maxAttempts}, reason=${reason || 'unknown'})`);
        console.log(`[WA] ${tenantId}: Reconnection strategy - next delay will be ${getReconnectDelay(attempts)/1000}s`);
        
        // Store attempts count before deleting session
        const reconnectAttempts = attempts;
        sessions.delete(tenantId);
        
        setTimeout(async () => {
          console.log(`[WA] ${tenantId}: ⏰ Starting reconnection attempt ${reconnectAttempts}...`);
          try {
            const newSession = await startSession(tenantId);
            if (newSession) {
              newSession.reconnectAttempts = reconnectAttempts;
            }
          } catch (e) {
            console.error(`[WA-ERROR] ${tenantId}: Reconnect failed:`, e.message);
          }
        }, delay);
      }
    } catch (e) { 
      console.error(`[WA-ERROR] ${tenantId}: connection.update error:`, e); 
    }
  });

  sock.ev.on('messages.upsert', async (payload) => {
    try {
      // ✅ FIX: סנן הודעות שהבוט שלח בעצמו (fromMe: true)
      const messages = payload.messages || [];
      
      // 🔍 DEBUG: Log all messages to see what's coming in
      console.log(`[${tenantId}] 🔔 ${messages.length} message(s) received, checking fromMe...`);
      messages.forEach((msg, idx) => {
        console.log(`[${tenantId}] Message ${idx}: fromMe=${msg.key?.fromMe}, remoteJid=${msg.key?.remoteJid}`);
      });
      
      const incomingMessages = messages.filter(msg => !msg.key.fromMe);
      
      if (incomingMessages.length === 0) {
        console.log(`[${tenantId}] ⏭️ Skipping ${messages.length} outgoing message(s) (fromMe: true)`);
        return;
      }
      
      console.log(`[${tenantId}] 📨 ${incomingMessages.length} incoming message(s) detected (from customer)`);
      
      // שלח רק הודעות נכנסות (לא הודעות שהבוט שלח)
      const filteredPayload = {
        ...payload,
        messages: incomingMessages
      };
      
      const response = await axios.post(`${FLASK_BASE_URL}/api/whatsapp/webhook/incoming`,
        { tenantId, payload: filteredPayload },
        { headers: { 'X-Internal-Secret': INTERNAL_SECRET } }
      );
      console.log(`[${tenantId}] ✅ Webhook→Flask success:`, response.status);
    } catch (e) { 
      console.error(`[${tenantId}] ❌ [Webhook→Flask] failed:`, e?.message || e);
      if (e.response) {
        console.error(`[${tenantId}] Flask response:`, e.response.status, e.response.data);
      }
    }
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
  server = app.listen(PORT, HOST, () => {
    const addr = server.address();
    console.log(`[BOOT] Baileys listening on ${HOST}:${addr.port} pid=${process.pid}`);
    console.log(`[BOOT] Docker networking: ${HOST === '0.0.0.0' ? '✅ accessible from other containers' : '⚠️ localhost only'}`);
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