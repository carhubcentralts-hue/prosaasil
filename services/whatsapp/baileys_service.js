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

const sessions = new Map(); // tenantId -> { sock, saveCreds, qrDataUrl, connected, starting, pushName, reconnectAttempts, authPaired, qrLock }

// 🔥 FIX: Track QR generation locks to prevent concurrent QR creation
const qrLocks = new Map(); // tenantId -> { locked: boolean, qrData: string, timestamp: number }

// 🔥 STEP 4 FIX: Track sending operations to prevent restart during send
const sendingLocks = new Map(); // tenantId -> { isSending: boolean, activeSends: number, lastSendTime: number }

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
  const forceRelink = req.body?.forceRelink || req.query?.forceRelink || false;  // 🔥 FIX: Support force relink
  
  const existing = sessions.get(tenantId);
  
  // 🔥 FIX: If forceRelink is requested, always proceed to clear and restart
  if (!forceRelink && existing && (existing.sock || existing.starting)) {
    console.log(`[${tenantId}] ⚠️ Already running or starting - skipping duplicate start`);
    return res.json({ok: true}); // כבר רץ
  }
  
  try { 
    console.log(`[${tenantId}] Starting session with forceRelink=${forceRelink}`);
    await startSession(tenantId, forceRelink); 
    res.json({ ok: true, forceRelink }); 
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
  const authPaired = !!s?.authPaired;  // 🔥 FIX: Include auth paired status
  const hasQR = !!s?.qrDataUrl;
  const reconnectAttempts = s?.reconnectAttempts || 0;
  
  // 🔧 ENHANCED: Return detailed diagnostic info
  // 🔥 FIX: Only report truly connected if BOTH socket open AND auth paired
  const truelyConnected = isConnected && authPaired;
  
  // 🔥 STEP 5 FIX: Separate "connected" from "canSend" capability
  // canSend requires: connected, has socket, authenticated, and not in error state
  const canSend = truelyConnected && hasSocket && !s?.starting;
  
  const diagnostics = {
    connected: truelyConnected,  // 🔥 FIX: Require both socket AND auth
    canSend: canSend,  // 🔥 STEP 5 FIX: Separate capability to send messages
    pushName: s?.pushName || '',
    hasQR: hasQR,
    hasSession,
    hasSocket,
    authPaired,  // 🔥 FIX: Expose auth paired status
    reconnectAttempts,
    sessionState: hasSession ? (truelyConnected ? 'connected' : (hasQR ? 'waiting_qr' : 'connecting')) : 'not_started',
    timestamp: new Date().toISOString()
  };
  
  console.log(`[WA] Status check for ${req.params.tenantId}: connected=${truelyConnected}, canSend=${canSend}`);
  return res.json(diagnostics);
});

// 🔥 STEP 4 FIX: New endpoint to check if service is currently sending messages
app.get('/whatsapp/:tenantId/sending-status', requireSecret, (req, res) => {
  const tenantId = req.params.tenantId;
  const lock = sendingLocks.get(tenantId);
  
  return res.json({
    isSending: lock?.isSending || false,
    activeSends: lock?.activeSends || 0,
    lastSendTime: lock?.lastSendTime || 0,
    idleTimeSec: lock?.lastSendTime ? Math.floor((Date.now() - lock.lastSendTime) / 1000) : null
  });
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
  
  // 🔥 ANDROID FIX: Check auth file validity
  let authFileStatus = 'not_found';
  let authValidationError = null;
  if (fs.existsSync(credsFile)) {
    try {
      const credsContent = fs.readFileSync(credsFile, 'utf8');
      const creds = JSON.parse(credsContent);
      if (creds.me && creds.me.id) {
        authFileStatus = 'valid';
      } else {
        authFileStatus = 'incomplete';
        authValidationError = 'Missing me.id in creds';
      }
    } catch (e) {
      authFileStatus = 'corrupted';
      authValidationError = e.message;
    }
  }
  
  // 🔧 FIX: Use actual configuration values instead of hardcoded
  const SOCKET_CONNECT_TIMEOUT = 30000;
  const SOCKET_QUERY_TIMEOUT = 20000;
  
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
      reconnect_attempts: s?.reconnectAttempts || 0,
      auth_paired: !!s?.authPaired
    },
    filesystem: {
      auth_path: authPath,
      auth_path_exists: fs.existsSync(authPath),
      qr_file_exists: fs.existsSync(qrFile),
      creds_file_exists: fs.existsSync(credsFile),
      auth_file_status: authFileStatus,
      auth_validation_error: authValidationError
    },
    config: {
      max_reconnect_attempts: RECONNECT_CONFIG.maxAttempts,
      base_delay_ms: RECONNECT_CONFIG.baseDelay,
      max_delay_ms: RECONNECT_CONFIG.maxDelay,
      connect_timeout_ms: SOCKET_CONNECT_TIMEOUT,
      query_timeout_ms: SOCKET_QUERY_TIMEOUT,
      qr_lock_timeout_ms: 180000  // 🔥 ANDROID FIX: 3 minutes
    },
    server: {
      port: PORT,
      host: HOST,
      total_sessions: sessions.size,
      uptime_seconds: Math.floor(process.uptime())
    }
  };
  
  // 🔧 FIX: Log only summary instead of full object
  console.log(`[WA] Diagnostics for ${tenantId}: state=${diagnostics.session.connected ? 'connected' : 'disconnected'}, attempts=${diagnostics.session.reconnect_attempts}, authStatus=${authFileStatus}`);
  return res.json(diagnostics);
});

// 🔥 ANDROID FIX: New endpoint to validate and cleanup auth state
app.post('/whatsapp/:tenantId/validate-auth', requireSecret, async (req, res) => {
  const tenantId = req.params.tenantId;
  const authPath = authDir(tenantId);
  const credsFile = path.join(authPath, 'creds.json');
  
  const result = {
    tenant_id: tenantId,
    timestamp: new Date().toISOString(),
    auth_valid: false,
    action_taken: 'none',
    message: ''
  };
  
  // Check if auth files exist
  if (!fs.existsSync(credsFile)) {
    result.message = 'No auth files found';
    return res.json(result);
  }
  
  // Validate auth files
  try {
    const credsContent = fs.readFileSync(credsFile, 'utf8');
    const creds = JSON.parse(credsContent);
    
    if (!creds.me || !creds.me.id) {
      // Auth incomplete - clean it up
      console.log(`[${tenantId}] 🧹 Cleaning incomplete auth files...`);
      fs.rmSync(authPath, { recursive: true, force: true });
      fs.mkdirSync(authPath, { recursive: true });
      
      result.action_taken = 'cleaned';
      result.message = 'Incomplete auth files cleaned - ready for fresh QR';
      
      // Clear session too
      sessions.delete(tenantId);
    } else {
      result.auth_valid = true;
      result.message = `Auth valid for phone: ${creds.me.id}`;
    }
  } catch (e) {
    // Auth corrupted - clean it up
    console.log(`[${tenantId}] 🧹 Cleaning corrupted auth files: ${e.message}`);
    try {
      fs.rmSync(authPath, { recursive: true, force: true });
      fs.mkdirSync(authPath, { recursive: true });
      
      result.action_taken = 'cleaned';
      result.message = `Corrupted auth files cleaned: ${e.message}`;
      
      // Clear session too
      sessions.delete(tenantId);
    } catch (cleanupError) {
      result.action_taken = 'failed';
      result.message = `Failed to clean auth: ${cleanupError.message}`;
      return res.status(500).json(result);
    }
  }
  
  return res.json(result);
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
    
    // 🔥 STEP 4 FIX: Acquire sending lock to prevent restart during send
    let lock = sendingLocks.get(tenantId);
    if (!lock) {
      lock = { isSending: false, activeSends: 0, lastSendTime: 0 };
      sendingLocks.set(tenantId, lock);
    }
    lock.isSending = true;
    lock.activeSends += 1;
    
    try {
      // 🔥 STEP 1 FIX: Add detailed logging before send
      console.log(`[BAILEYS] sending message to ${to.substring(0, 15)}..., tenantId=${tenantId}, textLength=${text.length}, activeSends=${lock.activeSends}`);
      
      // 🔥 STEP 1 FIX: Add timeout protection to prevent hanging (30s max)
      // This ensures we always return a response even if WhatsApp hangs
      const sendPromise = s.sock.sendMessage(to, { text: text });
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Send timeout after 30s')), 30000)
      );
      
      const result = await Promise.race([sendPromise, timeoutPromise]);
      
      const duration = Date.now() - startTime;
      // 🔥 STEP 1 FIX: Add detailed logging after send
      console.log(`[BAILEYS] send finished successfully, duration=${duration}ms, messageId=${result.key.id}, to=${to.substring(0, 15)}`);
      
      // Update lock state
      lock.activeSends -= 1;
      lock.lastSendTime = Date.now();
      if (lock.activeSends === 0) {
        lock.isSending = false;
      }
      
      return res.json({ 
        ok: true, 
        messageId: result.key.id,
        status: 'sent',
        duration_ms: duration
      });
    } catch (sendError) {
      // Update lock state on error
      lock.activeSends -= 1;
      if (lock.activeSends === 0) {
        lock.isSending = false;
      }
      throw sendError;
    }
    
  } catch (e) {
    const duration = Date.now() - startTime;
    console.error(`[BAILEYS] send failed, duration=${duration}ms, error=${e.message}, stack=${e.stack?.substring(0, 200)}`);
    return res.status(500).json({ 
      error: 'send_failed', 
      message: e.message,
      duration_ms: duration
    });
  }
});

/** Baileys session logic */
async function startSession(tenantId, forceRelink = false) {
  console.log(`[${tenantId}] 🚀 startSession called (forceRelink=${forceRelink})`);
  
  // 🔥 FIX: If forceRelink, delete old session completely
  if (forceRelink) {
    console.log(`[${tenantId}] 🔥 Force relink requested - clearing old session`);
    const existing = sessions.get(tenantId);
    if (existing?.sock) {
      try {
        console.log(`[${tenantId}] 🔚 Closing existing socket for force relink`);
        existing.sock.end();
        existing.sock.removeAllListeners();
      } catch (e) {
        console.error(`[${tenantId}] Socket cleanup error:`, e);
      }
    }
    sessions.delete(tenantId);
    
    // Delete auth files for fresh start
    const authPath = authDir(tenantId);
    try {
      console.log(`[${tenantId}] 🗑️ Clearing auth files from: ${authPath}`);
      fs.rmSync(authPath, { recursive: true, force: true });
      fs.mkdirSync(authPath, { recursive: true });
      console.log(`[${tenantId}] ✅ Auth files cleared - fresh session`);
    } catch (e) {
      console.error(`[${tenantId}] Auth cleanup error:`, e);
    }
  }
  
  const cur = sessions.get(tenantId);
  if (cur?.sock) return cur;
  if (cur?.starting) return cur;
  
  // 🔥 FIX: QR Lock - prevent concurrent QR generation
  const lock = qrLocks.get(tenantId);
  if (lock && lock.locked) {
    const age = Date.now() - lock.timestamp;
    if (age < 180000) { // 🔥 ANDROID FIX: Lock valid for 180 seconds (3 minutes) to accommodate slow Android scanning
      console.log(`[${tenantId}] ⚠️ QR generation already in progress (age=${Math.floor(age/1000)}s), returning existing lock`);
      return cur || { starting: true, qrDataUrl: lock.qrData || '' };
    } else {
      console.log(`[${tenantId}] 🔓 Releasing stale QR lock (age=${Math.floor(age/1000)}s)`);
      qrLocks.delete(tenantId);
    }
  }
  
  // Set lock
  qrLocks.set(tenantId, { locked: true, qrData: null, timestamp: Date.now() });
  
  sessions.set(tenantId, { starting: true });

  const authPath = authDir(tenantId);  // fs.mkdirSync(..., {recursive:true}) כבר קיים
  
  // 🔥 ANDROID FIX: Validate existing auth state before using it
  // If auth files are corrupted or incomplete, clear them to force fresh QR generation
  const credsFile = path.join(authPath, 'creds.json');
  if (fs.existsSync(credsFile)) {
    try {
      const credsContent = fs.readFileSync(credsFile, 'utf8');
      const creds = JSON.parse(credsContent);
      
      // Check if creds have essential fields
      if (!creds.me || !creds.me.id) {
        console.log(`[${tenantId}] ⚠️ Auth creds incomplete (missing me.id) - clearing for fresh start`);
        fs.rmSync(authPath, { recursive: true, force: true });
        fs.mkdirSync(authPath, { recursive: true });
      } else {
        console.log(`[${tenantId}] ✅ Auth creds validated - me.id=${creds.me.id}`);
      }
    } catch (e) {
      console.log(`[${tenantId}] ⚠️ Auth creds corrupted - clearing for fresh start: ${e.message}`);
      fs.rmSync(authPath, { recursive: true, force: true });
      fs.mkdirSync(authPath, { recursive: true });
    }
  }
  
  const { state, saveCreds } = await useMultiFileAuthState(authPath);

  // --- גרסה/דפדפן יציבים (מונע pairing תקוע) ---
  const { version } = await fetchLatestBaileysVersion();
  console.log(`[${tenantId}] 🔧 Using Baileys version:`, version);
  
  // ⚡ OPTIMIZED Baileys socket for maximum speed & reliability
  // 🔥 ANDROID FIX: Use proper browser identification that Android WhatsApp accepts
  // Format: ['App Name', 'OS/Browser', 'Version']
  // Must use real OS and version to avoid Android WhatsApp rejection
  const sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false,
    browser: ['Ubuntu', 'Chrome', '20.0.04'],  // 🔥 ANDROID FIX: Use realistic browser info (Ubuntu + Chrome + real version)
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

  const s = { sock, saveCreds, qrDataUrl: '', connected: false, pushName: '', starting: false, authPaired: false };
  sessions.set(tenantId, s);
  console.log(`[${tenantId}] 💾 Session stored in memory with stable browser settings`);

  sock.ev.on('creds.update', async () => {
    await saveCreds();
    s.authPaired = true;  // 🔥 FIX: Mark auth as paired when creds are saved
    console.log(`[${tenantId}] 🔐 Credentials saved to disk - authPaired=true`);
  });
  sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
    try {
      const reason = lastDisconnect?.error?.output?.statusCode;
      const reasonMessage = lastDisconnect?.error?.message || String(reason || '');
      
      // 🔧 ENHANCED: More detailed logging for connection diagnostics
      const timestamp = new Date().toISOString();
      console.log(`[WA] ${timestamp} connection update: tenant=${tenantId}, state=${connection || 'none'}, reason=${reason || 'none'}, reasonMsg=${reasonMessage || 'none'}, hasQR=${!!qr}, authPaired=${s.authPaired}`);
      
      // B2) לוגיקת QR יציבה בNode עם qr_code.txt
      const qrFile = path.join(authPath, 'qr_code.txt');
      
      if (qr) {
        // 🔧 ENHANCED: Add QR generation timing
        const qrStartTime = Date.now();
        s.qrDataUrl = await QRCode.toDataURL(qr);
        const qrDuration = Date.now() - qrStartTime;
        console.log(`[WA] ${tenantId}: ✅ QR generated successfully in ${qrDuration}ms, qr_length=${qr.length}`);
        
        // 🔥 FIX: Update QR lock with actual QR data
        const lock = qrLocks.get(tenantId);
        if (lock) {
          lock.qrData = s.qrDataUrl;
        }
        
        try { 
          fs.writeFileSync(qrFile, qr);
          console.log(`[WA] ${tenantId}: QR saved to file: ${qrFile}`);
        } catch(e) { 
          console.error(`[WA-ERROR] ${tenantId}: QR file write error:`, e); 
        }
      }
      
      if (connection === 'open') {
        // 🔥 ANDROID FIX: More robust auth paired detection
        // Check multiple indicators to ensure we're truly authenticated:
        // 1. creds.update event fired (s.authPaired)
        // 2. state has valid me.id
        // 3. socket has valid user info
        const hasAuthPaired = s.authPaired;
        const hasStateCreds = state && state.creds && state.creds.me && state.creds.me.id;
        const hasSockUser = sock && sock.user && sock.user.id;
        
        console.log(`[WA] ${tenantId}: Connection open - authPaired=${hasAuthPaired}, stateCreds=${!!hasStateCreds}, sockUser=${!!hasSockUser}`);
        
        // 🔥 ANDROID FIX: Wait for proper authentication before marking as connected
        // Android scans can complete socket connection before auth is fully paired
        if (!hasAuthPaired && !hasStateCreds && !hasSockUser) {
          console.log(`[WA] ${tenantId}: ⚠️ Socket open but no auth indicators yet - waiting for authentication`);
          // Wait a bit and check again
          setTimeout(() => {
            if (s.sock && !s.connected) {
              console.log(`[WA] ${tenantId}: ⚠️ Still not authenticated after 2s - might be auth failure`);
            }
          }, 2000);
          return;
        }
        
        s.connected = true; 
        s.authPaired = true;  // Ensure this is set
        s.qrDataUrl = '';
        s.pushName = sock?.user?.name || sock?.user?.id || '';
        s.reconnectAttempts = 0;  // 🔧 HARDENING 1.1: Reset reconnect counter on success
        const phoneNumber = sock?.user?.id || 'unknown';
        console.log(`[WA] ${tenantId}: ✅ Connected AND Paired! pushName=${s.pushName}, phone=${phoneNumber}, authPaired=true`);
        console.log(`[WA] ${tenantId}: Session info - id=${sock?.user?.id}, name=${sock?.user?.name}`);
        
        // 🔥 FIX: Release QR lock on successful connection
        qrLocks.delete(tenantId);
        console.log(`[WA] ${tenantId}: 🔓 QR lock released after successful pairing`);
        
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
        // 🔥 ANDROID FIX: Detect scan failure - close right after QR scan without pairing
        const wasScanningQR = s.qrDataUrl && !s.authPaired;
        const isAndroidScanFailure = wasScanningQR && (
          reason === 401 || // logged_out before auth complete
          reason === 428 || // connection lost during scan
          reason === 440 || // session replaced (another device scanning)
          !reason // undefined reason during QR scan often means scan rejected
        );
        
        if (isAndroidScanFailure) {
          console.log(`[WA] ${tenantId}: ❌ QR SCAN FAILED (Android/slow connection) - Connection closed before auth completed`);
          console.log(`[WA] ${tenantId}: Common causes: Invalid QR, network issue, WhatsApp rejected pairing, or slow scanning`);
          console.log(`[WA] ${tenantId}: Reason code: ${reason || 'none'}, Message: ${reasonMessage || 'none'}`);
          
          // 🔥 ANDROID FIX: Clear auth files to force fresh QR on retry
          try {
            console.log(`[WA] ${tenantId}: Clearing potentially corrupted auth files...`);
            fs.rmSync(authPath, { recursive: true, force: true });
            fs.mkdirSync(authPath, { recursive: true });
            console.log(`[WA] ${tenantId}: Auth files cleared - will generate fresh QR on reconnect`);
          } catch (e) {
            console.error(`[WA-ERROR] ${tenantId}: Failed to clear auth files:`, e);
          }
        }
        
        s.connected = false;
        s.authPaired = false;  // Reset auth paired state
        console.log(`[WA] ${tenantId}: ❌ Disconnected. reason=${reason}, message=${reasonMessage}, wasScanningQR=${wasScanningQR}, isAndroidFailure=${isAndroidScanFailure}`);
        console.log(`[WA] ${tenantId}: Disconnect details - reasonCode=${reason}, lastError=${JSON.stringify(lastDisconnect?.error || {})}`);
        
        // 🔥 FIX: Release QR lock on disconnect
        qrLocks.delete(tenantId);
        
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
          setTimeout(() => startSession(tenantId, true), 5000);  // Force relink
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
      
      // 🔍 ANDROID DEBUG: Enhanced logging for Android vs iPhone message detection
      console.log(`[${tenantId}] 🔔 ${messages.length} message(s) received, checking fromMe...`);
      messages.forEach((msg, idx) => {
        const fromMe = msg.key?.fromMe;
        const remoteJid = msg.key?.remoteJid;
        const pushName = msg.pushName || 'Unknown';
        console.log(`[${tenantId}] Message ${idx}: fromMe=${fromMe}, remoteJid=${remoteJid}, pushName=${pushName}`);
        
        // 🔥 ANDROID DEBUG: Log message structure to debug Android vs iPhone differences
        const messageKeys = Object.keys(msg.message || {});
        console.log(`[${tenantId}] Message ${idx} content keys: ${messageKeys.join(', ')}`);
        
        // 🔥 ANDROID FIX: Enhanced content logging for all message types
        const msgObj = msg.message || {};
        
        // Log each message type we support
        if (msgObj.conversation) {
          console.log(`[${tenantId}] Message ${idx} [conversation]: "${msgObj.conversation.substring(0, 50)}"`);
        }
        if (msgObj.extendedTextMessage?.text) {
          console.log(`[${tenantId}] Message ${idx} [extendedTextMessage]: "${msgObj.extendedTextMessage.text.substring(0, 50)}"`);
        }
        if (msgObj.imageMessage) {
          const caption = msgObj.imageMessage.caption || '(no caption)';
          console.log(`[${tenantId}] Message ${idx} [imageMessage] caption: "${caption}"`);
        }
        if (msgObj.videoMessage) {
          const caption = msgObj.videoMessage.caption || '(no caption)';
          console.log(`[${tenantId}] Message ${idx} [videoMessage] caption: "${caption}"`);
        }
        if (msgObj.audioMessage) {
          console.log(`[${tenantId}] Message ${idx} [audioMessage] detected`);
        }
        
        // 🔥 ANDROID DEBUG: If no known message type, log ALL keys to help debug
        if (!msgObj.conversation && !msgObj.extendedTextMessage && !msgObj.imageMessage && 
            !msgObj.videoMessage && !msgObj.audioMessage && !msgObj.documentMessage) {
          console.log(`[${tenantId}] Message ${idx} UNKNOWN FORMAT - Full keys: ${messageKeys.join(', ')}`);
          // Try to extract any text content
          messageKeys.forEach(key => {
            if (msgObj[key] && typeof msgObj[key] === 'object') {
              const subKeys = Object.keys(msgObj[key]);
              console.log(`[${tenantId}] Message ${idx} [${key}] subkeys: ${subKeys.join(', ')}`);
              if (msgObj[key].text) {
                console.log(`[${tenantId}] Message ${idx} [${key}.text]: "${String(msgObj[key].text).substring(0, 50)}"`);
              }
              if (msgObj[key].caption) {
                console.log(`[${tenantId}] Message ${idx} [${key}.caption]: "${String(msgObj[key].caption).substring(0, 50)}"`);
              }
            }
          });
        }
      });
      
      // 🔥 ANDROID FIX: Double-check filtering - use both fromMe AND our phone number
      // Sometimes Android messages are incorrectly marked as fromMe=true
      const ourUserId = sock?.user?.id; // Our bot's WhatsApp ID
      
      const incomingMessages = messages.filter(msg => {
        const fromMe = msg.key?.fromMe;
        const remoteJid = msg.key?.remoteJid;
        
        // 🔥 ANDROID FIX: If fromMe=true but remoteJid is NOT our number, it's likely a bug
        // Include it anyway if it looks like a customer message
        if (fromMe && remoteJid && ourUserId && remoteJid !== ourUserId) {
          console.log(`[${tenantId}] ⚠️ ANDROID BUG DETECTED: fromMe=true but remoteJid=${remoteJid} (not our ${ourUserId})`);
          console.log(`[${tenantId}] Including this message anyway - likely Android bug`);
          return true; // Include it!
        }
        
        return !fromMe;
      });
      
      if (incomingMessages.length === 0) {
        console.log(`[${tenantId}] ⏭️ Skipping ${messages.length} outgoing message(s) (fromMe: true)`);
        return;
      }
      
      console.log(`[${tenantId}] 📨 ${incomingMessages.length} incoming message(s) detected (from customer) - forwarding to Flask`);
      
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
  console.log(`[${tenantId}] 🔄 resetSession called - using forceRelink`);
  // 🔥 FIX: Use startSession with forceRelink=true instead of manual cleanup
  return await startSession(tenantId, true);
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