const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const axios = require('axios');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');

// 🔥 FIX #2: Version validation - Fail-fast if Baileys version mismatch
const EXPECTED_BAILEYS_VERSION = '6.7.5';
try {
  const packageJson = require('./package.json');
  const actualVersion = packageJson.dependencies['@whiskeysockets/baileys'];
  console.log(`[BOOT] 🔍 Baileys version check: expected=${EXPECTED_BAILEYS_VERSION}, package.json=${actualVersion}`);
  
  // Strip ^ or ~ if present
  const cleanVersion = actualVersion.replace(/[\^~]/, '');
  if (cleanVersion !== EXPECTED_BAILEYS_VERSION) {
    console.error(`[FATAL] ❌ Baileys version mismatch!`);
    console.error(`[FATAL] Expected: ${EXPECTED_BAILEYS_VERSION}`);
    console.error(`[FATAL] Found in package.json: ${actualVersion}`);
    console.error(`[FATAL] This will cause shouldSyncHistoryMessage and other API errors.`);
    console.error(`[FATAL] Fix: Update package.json to exactly "${EXPECTED_BAILEYS_VERSION}" (no ^ or ~)`);
    console.error(`[FATAL] Then run: npm install`);
    process.exit(1);
  }
  console.log(`[BOOT] ✅ Baileys version validated: ${EXPECTED_BAILEYS_VERSION}`);
} catch (e) {
  console.error(`[FATAL] Failed to validate Baileys version:`, e.message);
  process.exit(1);
}

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
// Base URL must come from env, never hardcode "backend"
const BACKEND_BASE_URL =
  process.env.BACKEND_BASE_URL ||
  process.env.API_BASE_URL ||
  'http://prosaas-api:5000';
const FLASK_BASE_URL = BACKEND_BASE_URL; // Alias for backwards compatibility

if (!INTERNAL_SECRET) {
  console.error('[FATAL] INTERNAL_SECRET missing');
  process.exit(1);
}

// 🔥 FIX #1: Wait for backend to be resolvable with retry
async function waitForBackendReady(maxAttempts = 10, delayMs = 2000) {
  console.log(`[BOOT] 🔍 Checking backend connectivity: ${FLASK_BASE_URL}`);
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const response = await axios.get(`${FLASK_BASE_URL}/api/health`, {
        headers: { 'X-Internal-Secret': INTERNAL_SECRET },
        timeout: 5000
      });
      
      if (response.status === 200) {
        console.log(`[BOOT] ✅ Backend is ready: ${FLASK_BASE_URL}`);
        return true;
      }
    } catch (err) {
      const errCode = err?.code || 'UNKNOWN';
      const errMsg = err?.message || String(err);
      console.log(`[BOOT] ⚠️ Backend not ready (attempt ${attempt}/${maxAttempts}): ${errCode} - ${errMsg}`);
      
      if (attempt < maxAttempts) {
        const waitTime = delayMs * Math.pow(1.5, attempt - 1); // Exponential backoff
        console.log(`[BOOT] ⏳ Waiting ${Math.floor(waitTime/1000)}s before retry...`);
        await new Promise(resolve => setTimeout(resolve, waitTime));
      }
    }
  }
  
  console.error(`[BOOT] ❌ Backend not reachable after ${maxAttempts} attempts: ${FLASK_BASE_URL}`);
  console.error(`[BOOT] ❌ Check BACKEND_BASE_URL and ensure prosaas-api is running`);
  process.exit(1);
}

// 🔥 CRITICAL FIX: Validate timezone is UTC to prevent clock drift issues
// WhatsApp requires accurate time synchronization - clock drift causes logged_out errors
const currentTZ = process.env.TZ || Intl.DateTimeFormat().resolvedOptions().timeZone;
if (currentTZ !== 'UTC' && currentTZ !== 'Etc/UTC') {
  console.warn(`[WARNING] ⚠️ Timezone is ${currentTZ}, not UTC. This may cause WhatsApp disconnections!`);
  console.warn(`[WARNING] ⚠️ Set TZ=UTC environment variable to fix clock drift issues.`);
  console.warn(`[WARNING] ⚠️ Current time: ${new Date().toISOString()}`);
} else {
  console.log(`[BOOT] ✅ Timezone correctly set to UTC: ${new Date().toISOString()}`);
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

// 🔥 CLOCK DIAGNOSTICS: Helper to check if clock is synchronized
function checkClockSync() {
  const now = Date.now();
  const isoTime = new Date(now).toISOString();
  const tz = process.env.TZ || Intl.DateTimeFormat().resolvedOptions().timeZone;
  const isUTC = (tz === 'UTC' || tz === 'Etc/UTC');
  
  return {
    unix_ms: now,
    iso: isoTime,
    timezone: tz,
    is_utc: isUTC,
    ok: isUTC,
    warning: isUTC ? null : `Clock is in ${tz} timezone, should be UTC for WhatsApp stability`
  };
}


const app = express();
app.use(cors());
app.use(express.json());

/** simple health BEFORE anything else */
app.get('/healthz', (req, res) => res.status(200).send('ok'));
app.get('/health', (req, res) => res.status(200).send('ok'));  // Add /health alias for Python compatibility
app.get('/', (req, res) => res.status(200).send('ok'));

// 🔥 CLOCK CHECK: Public endpoint to verify server time (no auth required for ops)
app.get('/clock', (req, res) => {
  const clockInfo = checkClockSync();
  const status = clockInfo.ok ? 200 : 500;
  return res.status(status).json(clockInfo);
});

// 🔥 CRITICAL FIX: Single source of truth for sessions
// Each session MUST have only ONE socket at any time (Iron Rule #1)
// Structure: { sock, saveCreds, qrDataUrl, connected, starting, pushName, reconnectAttempts, authPaired, createdAt, startingPromise, keysLock, canSend }
const sessions = new Map(); // tenantId -> session object

// 🔥 CRITICAL: Per-tenant mutex to prevent ANY concurrent socket creation
// This is the master lock that guards ALL socket operations for a tenant
const tenantMutex = new Map(); // tenantId -> { locked: boolean, queue: Promise[] }

// 🔥 FIX: Track QR generation locks to prevent concurrent QR creation
const qrLocks = new Map(); // tenantId -> { locked: boolean, qrData: string, timestamp: number }

// 🔥 FIX #4: Track session start operations to prevent duplicate starts
// This prevents race conditions when UI does refresh/polling/double-click during QR scan
// CRITICAL: Must be 180s (3 minutes) to cover full auth/pairing window (Android takes longer)
const STARTING_LOCK_MS = 180000;  // 3 minutes - same as QR validity
const startingLocks = new Map(); // tenantId -> { starting: boolean, timestamp: number, promise: Promise }

// 🔥 STEP 4 FIX: Track sending operations to prevent restart during send
const sendingLocks = new Map(); // tenantId -> { isSending: boolean, activeSends: number, lastSendTime: number }

// 🔥 FIX #3: Persistent message queue on filesystem (survives container restart)
const QUEUE_DIR = path.join(process.cwd(), 'storage', 'queue');
fs.mkdirSync(QUEUE_DIR, { recursive: true });

// Load queue from disk on startup
const messageQueue = [];
try {
  const queueFile = path.join(QUEUE_DIR, 'pending_messages.json');
  if (fs.existsSync(queueFile)) {
    const savedQueue = JSON.parse(fs.readFileSync(queueFile, 'utf8'));
    messageQueue.push(...savedQueue);
    console.log(`[BOOT] 📂 Loaded ${messageQueue.length} pending messages from disk`);
  }
} catch (e) {
  console.error(`[BOOT] ⚠️ Failed to load queue from disk:`, e.message);
}

// Save queue to disk periodically
function saveQueueToDisk() {
  try {
    const queueFile = path.join(QUEUE_DIR, 'pending_messages.json');
    fs.writeFileSync(queueFile, JSON.stringify(messageQueue, null, 2));
  } catch (e) {
    console.error(`[QUEUE] ⚠️ Failed to save queue to disk:`, e.message);
  }
}

// Auto-save every 30 seconds
setInterval(saveQueueToDisk, 30000);

const messageDedup = new Map(); // (tenantId:remoteJid:message_id) -> timestamp to prevent duplicates
const MAX_QUEUE_SIZE = 1000;
const MAX_RETRY_ATTEMPTS = 5;
const RETRY_BACKOFF_MS = [5000, 10000, 30000, 60000, 120000]; // 5s, 10s, 30s, 1m, 2m
// 🔥 CRITICAL FIX: Dedup cleanup must be LONGER than max retry time
// Max cumulative backoff time = 5s + 10s + 30s + 60s + 120s = 225s (3.75 minutes)
// Note: This is just backoff delays, actual elapsed time will be longer
// Set cleanup to 5 minutes to provide safe margin for retries
const DEDUP_CLEANUP_MS = 300000; // 5 minutes (300 seconds)
const DEDUP_CLEANUP_HOUR_MS = 300000; // 5 minutes for dedup entry retention
const DEDUP_MAX_SIZE = 5000; // Increased from 1000 for high-volume usage

// 🔥 PERFORMANCE FIX: Single cleanup interval with longer period to reduce CPU usage
// Cleanup dedup entries older than 5 minutes to prevent memory leaks
// This is longer than max retry time (3.75 min) to ensure retries work correctly
setInterval(() => {
  const now = Date.now();
  let cleaned = 0;
  
  for (const [key, timestamp] of messageDedup.entries()) {
    if (now - timestamp > DEDUP_CLEANUP_MS) {
      messageDedup.delete(key);
      cleaned++;
    }
  }
  
  if (cleaned > 0) {
    console.log(`[DEDUP] Cleaned ${cleaned} old entries from dedup map (size: ${messageDedup.size})`);
  }
  
  // 🔥 PERFORMANCE: Log memory usage every cleanup to detect leaks
  if (messageDedup.size > DEDUP_MAX_SIZE) {
    console.warn(`[DEDUP] ⚠️ Dedup map is large: ${messageDedup.size} entries (max: ${DEDUP_MAX_SIZE})`);
  }
}, 600000); // Run cleanup every 10 minutes (reduced from duplicate 5-minute intervals)

// 🔥 BUILD 200: Extract text from message with comprehensive format support
// Handles all WhatsApp message types and filters non-chat events
function extractText(msgObj) {
  // 🔥 CRITICAL: Filter out non-chat events that shouldn't go to Flask
  // These are system/protocol messages, not actual user messages
  // Note: messageContextInfo is metadata that can accompany real messages, so it's not filtered
  if (msgObj.pollUpdateMessage || 
      msgObj.protocolMessage || 
      msgObj.historySyncNotification ||
      msgObj.reactionMessage ||
      msgObj.senderKeyDistributionMessage) {
    return null;  // Ignore silently - these are not chat messages
  }
  
  // Try all possible text locations (order matters - most common first)
  // 1. Plain text conversation
  if (msgObj.conversation) {
    return msgObj.conversation;
  }
  
  // 2. Extended text message (with formatting, links, etc.)
  if (msgObj.extendedTextMessage?.text) {
    return msgObj.extendedTextMessage.text;
  }
  
  // 3. Media messages with captions
  if (msgObj.imageMessage?.caption) {
    return msgObj.imageMessage.caption;
  }
  
  if (msgObj.videoMessage?.caption) {
    return msgObj.videoMessage.caption;
  }
  
  if (msgObj.documentMessage?.caption) {
    return msgObj.documentMessage.caption;
  }
  
  // 4. Interactive messages (buttons, lists, templates)
  if (msgObj.buttonsResponseMessage?.selectedDisplayText) {
    return msgObj.buttonsResponseMessage.selectedDisplayText;
  }
  
  if (msgObj.listResponseMessage?.title) {
    return msgObj.listResponseMessage.title;
  }
  
  if (msgObj.listResponseMessage?.description) {
    return msgObj.listResponseMessage.description;
  }
  
  if (msgObj.templateButtonReplyMessage?.selectedDisplayText) {
    return msgObj.templateButtonReplyMessage.selectedDisplayText;
  }
  
  // 5. Audio and document messages are valid but may have no text content
  // Note: Documents WITH captions are handled above (line 278)
  // This section handles audio messages and documents WITHOUT captions
  // Still send to Flask so it can handle media appropriately
  if (msgObj.audioMessage || msgObj.documentMessage) {
    return '[media]';  // Return indicator that this is valid content
  }
  
  // 6. Location messages
  if (msgObj.locationMessage) {
    return '[location]';  // Return indicator for location sharing
  }
  
  // 7. Contact messages
  if (msgObj.contactMessage || msgObj.contactsArrayMessage) {
    return '[contact]';  // Return indicator for contact sharing
  }
  
  return null;  // No extractable text - likely a system message
}

// Helper function to check if a message has actual content
function hasTextContent(msgObj) {
  return extractText(msgObj) !== null;
}


// 🔥 FIX #1: Process message queue periodically
setInterval(() => {
  if (messageQueue.length === 0) return;
  
  const now = Date.now();
  const toRetry = [];
  
  // Find messages ready for retry
  for (let i = messageQueue.length - 1; i >= 0; i--) {
    const item = messageQueue[i];
    const backoffDelay = RETRY_BACKOFF_MS[Math.min(item.attempts, RETRY_BACKOFF_MS.length - 1)];
    
    if (now - item.lastAttempt >= backoffDelay) {
      toRetry.push(item);
      messageQueue.splice(i, 1);
    }
  }
  
  // Retry messages
  toRetry.forEach(item => {
    retryWebhookDelivery(item);
  });
}, 10000); // Check every 10 seconds

async function retryWebhookDelivery(item) {
  const { tenantId, messageId, remoteJid, payload, attempts } = item;
  
  try {
    console.log(`[${tenantId}] 🔄 Retrying webhook delivery (attempt ${attempts + 1}/${MAX_RETRY_ATTEMPTS})`);
    
    const response = await axios.post(`${FLASK_BASE_URL}/api/whatsapp/webhook/incoming`,
      payload,
      { 
        headers: { 
          'Content-Type': 'application/json',
          'X-Internal-Secret': INTERNAL_SECRET 
        },
        timeout: 10000
      }
    );
    
    console.log(`[${tenantId}] ✅ Webhook retry succeeded: ${response.status}`);
    // Remove from dedup map after successful delivery using correct key format
    const dedupKey = `${tenantId}:${remoteJid}:${messageId}`;
    messageDedup.delete(dedupKey);
    
    // 🔥 FIX #3: Save queue after successful delivery
    saveQueueToDisk();
    
  } catch (e) {
    console.error(`[${tenantId}] ❌ Webhook retry failed (attempt ${attempts + 1}):`, e?.message || e);
    
    // Re-queue if under max attempts
    if (attempts + 1 < MAX_RETRY_ATTEMPTS) {
      item.attempts += 1;
      item.lastAttempt = Date.now();
      messageQueue.push(item);
      console.log(`[${tenantId}] 📝 Message re-queued for retry (${attempts + 2}/${MAX_RETRY_ATTEMPTS})`);
      
      // 🔥 FIX #3: Save queue after re-queueing
      saveQueueToDisk();
    } else {
      console.error(`[${tenantId}] ❌ Max retry attempts reached - dropping message ${messageId}`);
      // Use correct dedup key format when removing
      // If remoteJid is missing, log warning but still try to delete
      if (remoteJid) {
        const dedupKey = `${tenantId}:${remoteJid}:${messageId}`;
        messageDedup.delete(dedupKey);
      } else {
        console.warn(`[${tenantId}] ⚠️ No remoteJid for message ${messageId} - cannot remove from dedup`);
      }
      
      // 🔥 FIX #3: Save queue after dropping message
      saveQueueToDisk();
    }
  }
}

// 🔧 HARDENING 1.1: Exponential backoff configuration for reconnection
// 🔥 FIX: Increased resilience for slow/unstable connections
const RECONNECT_CONFIG = {
  baseDelay: 5000,    // 5 seconds
  maxDelay: 120000,   // 🔧 Increased from 60s to 120s (2 minutes max)
  multiplier: 1.5,    // 🔧 Reduced from 2 to 1.5 for gentler backoff
  maxAttempts: 20     // 🔧 Increased from 10 to 20 attempts - don't give up easily!
};

// 🔥 ANDROID FIX: QR code validity timeout
// Android devices are often slower to scan QR codes than iPhones
// This timeout prevents creating new QR codes while user is still scanning
const QR_VALIDITY_MS = 180000;  // 3 minutes (180 seconds)

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

// 🔥 ANDROID FIX: Helper to safely close existing socket
// This prevents duplicate sockets by ensuring old one is fully closed before creating new one
async function safeClose(sock, tenantId) {
  if (!sock) return;
  
  console.log(`[${tenantId}] 🔚 safeClose: Closing existing socket...`);
  try {
    // 🔥 FIX #5: Safely remove listeners - check if method exists
    // Different Baileys versions may have different event emitter structures
    if (sock.ev && typeof sock.ev.removeAllListeners === 'function') {
      sock.ev.removeAllListeners();
    } else if (typeof sock.removeAllListeners === 'function') {
      sock.removeAllListeners();
    } else {
      console.log(`[${tenantId}] ⚠️ safeClose: No removeAllListeners method found`);
    }
    
    // End the socket connection
    if (typeof sock.end === 'function') {
      sock.end();
    } else if (typeof sock.close === 'function') {
      sock.close();
    } else {
      console.log(`[${tenantId}] ⚠️ safeClose: No end/close method found`);
    }
    
    // Wait a bit for socket to fully close
    await new Promise(resolve => setTimeout(resolve, 500));
    
    console.log(`[${tenantId}] ✅ safeClose: Socket closed successfully`);
  } catch (e) {
    console.error(`[${tenantId}] ⚠️ safeClose: Error during close:`, e.message);
  }
}

// 🔥 ANDROID FIX: Wait for socket to be fully closed before proceeding
// This ensures no race conditions where old socket is still active when new one starts
async function waitForSockClosed(tenantId, timeoutMs = 2000) {
  console.log(`[${tenantId}] ⏳ waitForSockClosed: Waiting ${timeoutMs}ms for socket cleanup...`);
  await new Promise(resolve => setTimeout(resolve, timeoutMs));
  console.log(`[${tenantId}] ✅ waitForSockClosed: Wait complete`);
}

function requireSecret(req, res, next) {
  if (req.header('X-Internal-Secret') !== INTERNAL_SECRET) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  next();
}

// 🔥 CRITICAL: Per-tenant mutex implementation
// This ensures only ONE operation can modify a tenant's session at a time
async function acquireTenantLock(tenantId) {
  // 🔥 FIX: Ensure lock object is always in the map
  if (!tenantMutex.has(tenantId)) {
    tenantMutex.set(tenantId, { locked: false, queue: [] });
  }
  
  const lock = tenantMutex.get(tenantId);
  
  // If already locked, wait in queue
  if (lock.locked) {
    await new Promise(resolve => {
      lock.queue.push(resolve);
    });
  }
  
  lock.locked = true;
  console.log(`[${tenantId}] 🔒 Tenant mutex acquired`);
}

function releaseTenantLock(tenantId) {
  const lock = tenantMutex.get(tenantId);
  if (!lock) {
    console.log(`[${tenantId}] ⚠️ Attempted to release non-existent lock`);
    return;
  }
  
  // Process next in queue
  if (lock.queue.length > 0) {
    const resolve = lock.queue.shift();
    resolve();
  } else {
    lock.locked = false;
  }
  
  console.log(`[${tenantId}] 🔓 Tenant mutex released (queue: ${lock.queue.length})`);
}

// 🔥 CRITICAL: Single entrypoint for ALL socket operations
// This is the ONLY function that should create or return socket instances
// ALL other code paths MUST call this function
async function getOrCreateSession(tenantId, reason = 'unknown', forceRelink = false) {
  console.log(`[${tenantId}] 🎯 getOrCreateSession called: reason=${reason}, forceRelink=${forceRelink}`);
  
  // Acquire mutex - blocks all concurrent operations for this tenant
  await acquireTenantLock(tenantId);
  
  try {
    // Check if session already exists and is usable
    const existing = sessions.get(tenantId);
    
    // If forceRelink, clean up everything
    if (forceRelink) {
      console.log(`[${tenantId}] 🔥 Force relink - clearing session`);
      if (existing?.sock) {
        await safeClose(existing.sock, tenantId);
        await waitForSockClosed(tenantId, 2000);
      }
      sessions.delete(tenantId);
      startingLocks.delete(tenantId);
      
      // Clear auth files
      const authPath = authDir(tenantId);
      try {
        fs.rmSync(authPath, { recursive: true, force: true });
        fs.mkdirSync(authPath, { recursive: true });
      } catch (e) {
        console.error(`[${tenantId}] Auth cleanup error:`, e);
      }
    }
    
    // 🔥 CORRECTED: Return existing session if sock exists (regardless of connected state)
    // Don't create a new socket if one already exists - prevents dual sockets
    if (!forceRelink && existing?.sock) {
      console.log(`[${tenantId}] ✅ Returning existing session (has sock, connected=${existing.connected}, starting=${existing.starting})`);
      return existing;
    }
    
    // Check if startSession is in progress - always wait for it
    const startLock = startingLocks.get(tenantId);
    if (!forceRelink && startLock && startLock.promise) {
      const lockAge = Date.now() - startLock.timestamp;
      if (lockAge < STARTING_LOCK_MS) {
        console.log(`[${tenantId}] ⏳ Start in progress - awaiting existing promise (age=${Math.floor(lockAge/1000)}s)`);
        return await startLock.promise;
      } else {
        console.log(`[${tenantId}] ⚠️ Stale starting lock detected (age=${Math.floor(lockAge/1000)}s) - clearing`);
        startingLocks.delete(tenantId);
      }
    }
    
    // Create new session only if no sock exists and no start in progress
    console.log(`[${tenantId}] 🚀 Creating new session via startSession`);
    return await startSession(tenantId, forceRelink);
    
  } finally {
    releaseTenantLock(tenantId);
  }
}

/** REST API (always the same app instance) */
/**
 * POST /whatsapp/:tenantId/start
 * 
 * Start or restart WhatsApp session for a tenant.
 * 
 * Parameters:
 *   - forceRelink (optional, boolean): If true, clears all existing session data and auth files
 *                                      for a completely fresh start. Use this when:
 *                                      - Android device won't connect after scanning QR
 *                                      - Getting 401/403/440 errors
 *                                      - Switching between Android and iPhone
 *                                      - WhatsApp says "Phone not connected"
 * 
 * Usage:
 *   POST /whatsapp/business_4/start
 *   Body: {"forceRelink": true}
 *   
 *   OR
 *   
 *   POST /whatsapp/business_4/start?forceRelink=true
 * 
 * Returns:
 *   200 OK: {"ok": true, "forceRelink": false, "state": "started"}
 *   409 Conflict: {"error": "start_in_progress"} - Another start is already in progress
 *   500 Error: {"error": "start_failed", "message": "..."} - Failed to start
 */
app.post('/whatsapp/:tenantId/start', requireSecret, async (req, res) => {
  const tenantId = req.params.tenantId;
  const forceRelink = req.body?.forceRelink || req.query?.forceRelink || false;
  
  console.log(`[${tenantId}] 📞 /start called: forceRelink=${forceRelink}`);
  
  try {
    // Use unified getOrCreateSession - the ONLY way to get/create a session
    await getOrCreateSession(tenantId, 'api_start', forceRelink);
    res.json({ ok: true, forceRelink, state: 'started' });
  } catch (e) {
    console.error(`[${tenantId}] ❌ start error:`, e.message);
    if (e.message === 'SESSION_START_IN_PROGRESS') {
      res.status(409).json({ error: 'start_in_progress' });
    } else {
      res.status(500).json({ error: 'start_failed', message: e.message });
    }
  }
});
app.get('/whatsapp/:tenantId/status', requireSecret, (req, res) => {
  const s = sessions.get(req.params.tenantId);
  const hasSession = !!s;
  const hasSocket = !!s?.sock;
  const isConnected = !!s?.connected;
  const authPaired = !!s?.authPaired;
  const hasQR = !!s?.qrDataUrl;
  const reconnectAttempts = s?.reconnectAttempts || 0;
  
  // 🔧 ENHANCED: Return detailed diagnostic info
  const truelyConnected = isConnected && authPaired;
  
  // 🔥 CORRECTED: canSend based on actual send verification, not presence test
  // Will be false until first message is successfully sent
  const canSend = s?.canSend || false;
  
  const diagnostics = {
    connected: truelyConnected,
    canSend: canSend,  // 🔥 CORRECTED: Based on actual first send success
    pushName: s?.pushName || '',
    hasQR: hasQR,
    hasSession,
    hasSocket,
    authPaired,
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
    clock: {
      // 🔥 CRITICAL: Clock diagnostics to detect drift
      current_time_iso: new Date().toISOString(),
      current_time_unix_ms: Date.now(),
      timezone: process.env.TZ || Intl.DateTimeFormat().resolvedOptions().timeZone,
      is_utc: (process.env.TZ === 'UTC' || process.env.TZ === 'Etc/UTC'),
      locale: Intl.DateTimeFormat().resolvedOptions().locale || 'unknown',
      // To check drift: compare current_time_unix_ms with real time
      // If difference > 60 seconds, there's clock drift!
      warning: (process.env.TZ !== 'UTC' && process.env.TZ !== 'Etc/UTC') ? 'TZ is not UTC - may cause disconnections!' : null
    },
    config: {
      max_reconnect_attempts: RECONNECT_CONFIG.maxAttempts,
      base_delay_ms: RECONNECT_CONFIG.baseDelay,
      max_delay_ms: RECONNECT_CONFIG.maxDelay,
      connect_timeout_ms: SOCKET_CONNECT_TIMEOUT,
      query_timeout_ms: SOCKET_QUERY_TIMEOUT,
      qr_lock_timeout_ms: 180000,  // 🔥 ANDROID FIX: 3 minutes
      browser_string: 'Baileys default (not overridden)'  // 🔥 FIX #1: Using Baileys default browser
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

// 🔥 NEW: JID resolution endpoint for @lid → phone_e164 mapping
// This endpoint attempts to resolve a WhatsApp JID to a real phone number
app.post('/internal/resolve-jid', async (req, res) => {
  try {
    const { jid, tenantId, participant, pushName } = req.body;
    
    if (!jid) {
      return res.status(400).json({ error: 'Missing jid parameter' });
    }
    
    if (!tenantId) {
      return res.status(400).json({ error: 'Missing tenantId parameter' });
    }
    
    const s = sessions.get(tenantId);
    
    if (!s || !s.sock || !s.connected) {
      return res.status(503).json({ error: 'WhatsApp not connected' });
    }
    
    // 🔥 Resolution strategy for @lid JIDs:
    // 1. Check if JID is actually @s.whatsapp.net (direct phone extraction)
    // 2. Try to get contact info from Baileys store
    // 3. Check recent message history for participant mapping
    // 4. Return null if cannot resolve (Flask will use mapping table)
    
    let phone_e164 = null;
    
    // Strategy 1: Direct extraction from @s.whatsapp.net
    if (jid.endsWith('@s.whatsapp.net')) {
      const phoneDigits = jid.split('@')[0].split(':')[0];
      if (phoneDigits && /^\d{10,15}$/.test(phoneDigits)) {
        // Format to E.164
        phone_e164 = '+' + phoneDigits;
        console.log(`[JID-RESOLVE] ${tenantId}: Direct extraction: ${jid} → ${phone_e164}`);
        return res.json({ phone_e164, source: 'direct' });
      }
    }
    
    // Strategy 2: Check Baileys store/contacts
    // Note: Baileys doesn't maintain a persistent contacts store in this configuration
    // This is a placeholder for future enhancement if store is added
    
    // Strategy 3: Return null - let Flask use mapping table
    console.log(`[JID-RESOLVE] ${tenantId}: Cannot resolve ${jid} - no store available`);
    return res.json({ phone_e164: null, source: 'unresolvable' });
    
  } catch (e) {
    console.error(`[JID-RESOLVE] Error: ${e.message}`);
    return res.status(500).json({ error: 'resolution_failed', message: e.message });
  }
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
    const { to, text, type = 'text', media, caption, tenantId } = req.body;
    
    // 🔥 FIX: Support both text messages and media messages
    // For text: requires 'to' and 'text'
    // For media: requires 'to' and 'media' object with {data, mimetype, filename}
    if (!to) {
      return res.status(400).json({ error: 'Missing required field: to' });
    }
    
    // Check if this is media message or text message
    const isMediaMessage = media && media.data && media.mimetype;
    
    if (!isMediaMessage && !text) {
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
      // 🔥 FIX: Support media messages
      let messageContent;
      
      if (isMediaMessage) {
        // Media message (image/video/audio/document)
        console.log(`[BAILEYS] sending ${type} media to ${to.substring(0, 15)}..., tenantId=${tenantId}, mime=${media.mimetype}, size=${media.data.length} chars`);
        
        // Decode base64 data to Buffer
        const mediaBuffer = Buffer.from(media.data, 'base64');
        
        // Build message content based on media type
        if (type === 'image') {
          messageContent = {
            image: mediaBuffer,
            caption: caption || text || '',
            mimetype: media.mimetype,
            fileName: media.filename || 'image.jpg'
          };
        } else if (type === 'video') {
          messageContent = {
            video: mediaBuffer,
            caption: caption || text || '',
            mimetype: media.mimetype,
            fileName: media.filename || 'video.mp4'
          };
        } else if (type === 'audio') {
          messageContent = {
            audio: mediaBuffer,
            mimetype: media.mimetype,
            fileName: media.filename || 'audio.mp3'
          };
        } else if (type === 'document') {
          messageContent = {
            document: mediaBuffer,
            mimetype: media.mimetype,
            fileName: media.filename || 'document.pdf',
            caption: caption || text || ''
          };
        } else {
          // Fallback to document with extension from mimetype
          const ext = media.mimetype ? media.mimetype.split('/')[1] : 'bin';
          messageContent = {
            document: mediaBuffer,
            mimetype: media.mimetype,
            fileName: media.filename || `file.${ext}`
          };
        }
      } else {
        // Text message
        console.log(`[BAILEYS] sending message to ${to.substring(0, 15)}..., tenantId=${tenantId}, textLength=${text.length}, activeSends=${lock.activeSends}`);
        messageContent = { text: text };
      }
      
      // 🔥 STEP 1 FIX: Add timeout protection to prevent hanging (30s max)
      // This ensures we always return a response even if WhatsApp hangs
      const sendPromise = s.sock.sendMessage(to, messageContent);
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Send timeout after 30s')), 30000)
      );
      
      const result = await Promise.race([sendPromise, timeoutPromise]);
      
      const duration = Date.now() - startTime;
      // 🔥 CORRECTED: Mark canSend=true after first successful send
      if (!s.canSend) {
        s.canSend = true;
        console.log(`[BAILEYS] ${tenantId}: ✅ First message sent successfully - canSend=true`);
      }
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
  
  // 🔥 ANDROID FIX A: Strict single-flight with promise tracking
  // Check if another startSession is already in progress for this tenant
  const existingStartLock = startingLocks.get(tenantId);
  if (!forceRelink && existingStartLock && existingStartLock.starting) {
    const lockAge = Date.now() - existingStartLock.timestamp;
    if (lockAge < STARTING_LOCK_MS) { // Lock valid for 180 seconds (3 minutes)
      console.log(`[${tenantId}] ⚠️ startSession already in progress (age=${Math.floor(lockAge/1000)}s) - returning existing promise`);
      if (existingStartLock.promise) {
        return await existingStartLock.promise;
      }
      throw new Error('SESSION_START_IN_PROGRESS');
    } else {
      console.log(`[${tenantId}] 🔓 Releasing stale starting lock (age=${Math.floor(lockAge/1000)}s)`);
      startingLocks.delete(tenantId);
    }
  }
  
  // 🔥 ANDROID FIX B: Close existing socket BEFORE creating new one
  const cur = sessions.get(tenantId);
  
  // If forceRelink, always close and clear everything
  if (forceRelink) {
    console.log(`[${tenantId}] 🔥 Force relink requested - clearing old session completely`);
    startingLocks.delete(tenantId); // Clear any locks
    
    if (cur?.sock) {
      await safeClose(cur.sock, tenantId);
      await waitForSockClosed(tenantId, 2000); // Wait 2 seconds for full cleanup
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
  
  // 🔥 ANDROID FIX: If session exists with active authenticated socket, return it (don't create new)
  if (!forceRelink && cur?.sock && cur.connected && cur.authPaired) {
    console.log(`[${tenantId}] ✅ Returning existing authenticated session (connected=${cur.connected})`);
    return cur;
  }
  
  // If session is starting, wait for it (single-flight)
  if (!forceRelink && cur?.starting) {
    console.log(`[${tenantId}] ⚠️ Session already starting, checking for promise...`);
    const lock = startingLocks.get(tenantId);
    if (lock?.promise) {
      console.log(`[${tenantId}] ⏳ Waiting for existing startSession promise...`);
      return await lock.promise;
    }
  }
  
  // 🔥 ANDROID FIX: If existing socket but not connected, close it before starting new
  if (cur?.sock && !cur.connected) {
    console.log(`[${tenantId}] 🔄 Existing socket found but not connected - closing before restart`);
    await safeClose(cur.sock, tenantId);
    await waitForSockClosed(tenantId, 2000);
    sessions.delete(tenantId);
  }
  
  // 🔥 ANDROID FIX A: Create promise for this start operation (single-flight)
  let resolvePromise, rejectPromise;
  const startPromise = new Promise((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });
  
  // Set starting lock BEFORE any async operations with promise
  startingLocks.set(tenantId, { 
    starting: true, 
    timestamp: Date.now(),
    promise: startPromise 
  });
  
  // 🔥 FIX: QR Lock - prevent concurrent QR generation
  const lock = qrLocks.get(tenantId);
  if (lock && lock.locked) {
    const age = Date.now() - lock.timestamp;
    if (age < QR_VALIDITY_MS) {
      console.log(`[${tenantId}] ⚠️ QR generation already in progress (age=${Math.floor(age/1000)}s)`);
      // Don't reject, just log - we'll create new QR if needed
    } else {
      console.log(`[${tenantId}] 🔓 Releasing stale QR lock (age=${Math.floor(age/1000)}s)`);
      qrLocks.delete(tenantId);
    }
  }
  
  // Set QR lock
  qrLocks.set(tenantId, { locked: true, qrData: null, timestamp: Date.now() });
  
  // Create initial session marker
  sessions.set(tenantId, { 
    starting: true, 
    connected: false, 
    authPaired: false,
    createdAt: Date.now()
  });

  const authPath = authDir(tenantId);
  
  try {
    // 🔥 ANDROID FIX: Validate existing auth state before using it
    const credsFile = path.join(authPath, 'creds.json');
    if (fs.existsSync(credsFile)) {
      try {
        const credsContent = fs.readFileSync(credsFile, 'utf8');
        const creds = JSON.parse(credsContent);
        
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

    const { version } = await fetchLatestBaileysVersion();
    console.log(`[${tenantId}] 🔧 Using Baileys version:`, version);
    
    // 🔥 ANDROID FIX: Log socket creation to track duplicate starts
    const creationTimestamp = new Date().toISOString();
    console.log(`[SOCK_CREATE] tenant=${tenantId}, ts=${creationTimestamp}, reason=start, forceRelink=${forceRelink}`);
    
    // Create Baileys socket
    const sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: false,
      markOnlineOnConnect: false,
      syncFullHistory: false,
      // 🔥 FIX #2: Guard against missing shouldSyncHistoryMessage function
      // Some Baileys versions don't have this function - provide safe fallback
      shouldSyncHistoryMessage: typeof state.shouldSyncHistoryMessage === 'function' 
        ? state.shouldSyncHistoryMessage 
        : () => false,  // Default: don't sync history
      getMessage: async () => undefined,
      defaultQueryTimeoutMs: 20000,
      connectTimeoutMs: 30000,
      retryRequestDelayMs: 500,
      maxMsgRetryCount: 5,
      keepAliveIntervalMs: 30000
    });

    const s = { 
      sock, 
      saveCreds, 
      qrDataUrl: '', 
      connected: false, 
      pushName: '', 
      starting: true, 
      authPaired: false,
      createdAt: Date.now(),
      keysLock: false,  // 🔥 ANDROID FIX C: Add lock for keys operations
      canSend: false    // 🔥 CORRECTED: Will be set to true after first successful send
    };
    sessions.set(tenantId, s);
    console.log(`[${tenantId}] 💾 Session stored in memory with Baileys default browser`);

    // 🔥 ANDROID FIX C: Mutex for BOTH creds and keys operations
    // This prevents concurrent writes that corrupt auth state
    // Note: Using busy-wait is acceptable here because:
    // - Lock durations are very short (auth writes are fast)
    // - Concurrent auth operations are rare
    // - 100ms interval prevents CPU spinning
    // - Max timeout prevents infinite loops
    let credsLock = false;
    const MAX_LOCK_WAIT_MS = 30000; // 30 seconds max wait
    
    async function waitForLock() {
      const startTime = Date.now();
      while (credsLock || s.keysLock) {
        if (Date.now() - startTime > MAX_LOCK_WAIT_MS) {
          throw new Error('Lock wait timeout - possible deadlock');
        }
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }
    
    sock.ev.on('creds.update', async () => {
      // Wait for any ongoing save to complete
      await waitForLock();
      
      credsLock = true;
      try {
        await saveCreds();
        s.authPaired = true;
        console.log(`[${tenantId}] 🔐 Credentials saved to disk - authPaired=true`);
      } catch (e) {
        console.error(`[${tenantId}] ❌ Failed to save credentials:`, e);
      } finally {
        credsLock = false;
      }
    });
    
    // 🔥 ANDROID FIX C: Wrap keys operations with mutex
    // This ensures keys.set/get are serialized with saveCreds
    const originalKeysSet = state.keys?.set;
    const originalKeysGet = state.keys?.get;
    
    if (state.keys && originalKeysSet) {
      state.keys.set = async function(...args) {
        await waitForLock();
        s.keysLock = true;
        try {
          return await originalKeysSet.apply(this, args);
        } finally {
          s.keysLock = false;
        }
      };
    }
    
    if (state.keys && originalKeysGet) {
      state.keys.get = async function(...args) {
        await waitForLock();
        s.keysLock = true;
        try {
          return await originalKeysGet.apply(this, args);
        } finally {
          s.keysLock = false;
        }
      };
    }
    
    sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
      try {
        const reason = lastDisconnect?.error?.output?.statusCode;
        const reasonMessage = lastDisconnect?.error?.message || String(reason || '');
        const errorPayload = lastDisconnect?.error?.output?.payload;
        
        const timestamp = new Date().toISOString();
        console.log(`[WA] ${timestamp} connection update: tenant=${tenantId}, state=${connection || 'none'}, reason=${reason || 'none'}, reasonMsg=${reasonMessage || 'none'}, hasQR=${!!qr}, authPaired=${s.authPaired}`);
        
        if (lastDisconnect && reason) {
          console.log(`[WA-DIAGNOSTIC] ${tenantId}: 🔍 DISCONNECT REASON DETAILS:`);
          console.log(`[WA-DIAGNOSTIC] ${tenantId}: - statusCode: ${reason}`);
          console.log(`[WA-DIAGNOSTIC] ${tenantId}: - payload: ${errorPayload ? JSON.stringify(errorPayload) : 'none'}`);
          console.log(`[WA-DIAGNOSTIC] ${tenantId}: - message: ${reasonMessage}`);
          
          if (reason === 401) {
            console.log(`[WA-DIAGNOSTIC] ${tenantId}: ⚠️ 401 = WhatsApp rejected authentication (unauthorized)`);
          } else if (reason === 403) {
            console.log(`[WA-DIAGNOSTIC] ${tenantId}: ⚠️ 403 = WhatsApp denied access (forbidden)`);
          } else if (reason === 428) {
            console.log(`[WA-DIAGNOSTIC] ${tenantId}: ⚠️ 428 = Connection prerequisite failed`);
          } else if (reason === 515) {
            console.log(`[WA-DIAGNOSTIC] ${tenantId}: ⚠️ 515 = WhatsApp server requested restart`);
          } else if (reason === 440) {
            console.log(`[WA-DIAGNOSTIC] ${tenantId}: ⚠️ 440 = Session replaced by another device`);
          }
        }
        
        const qrFile = path.join(authPath, 'qr_code.txt');
        
        if (qr) {
          const qrStartTime = Date.now();
          s.qrDataUrl = await QRCode.toDataURL(qr);
          s.qrGeneratedAt = Date.now();
          const qrDuration = Date.now() - qrStartTime;
          console.log(`[WA] ${tenantId}: ✅ QR generated successfully in ${qrDuration}ms, qr_length=${qr.length}, timestamp=${s.qrGeneratedAt}`);
          
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
          // 🔥 CORRECTED: Only mark connected after proper validation
          // Check required fields exist
          const hasAuthPaired = s.authPaired;
          const hasStateCreds = state && state.creds && state.creds.me && state.creds.me.id;
          const hasSockUser = sock && sock.user && sock.user.id;
          
          console.log(`[WA] ${tenantId}: Connection open - checking auth: authPaired=${hasAuthPaired}, stateCreds=${!!hasStateCreds}, sockUser=${!!hasSockUser}`);
          
          // All fields must exist before marking connected
          if (!hasSockUser || !hasStateCreds) {
            console.log(`[WA] ${tenantId}: ⚠️ Socket open but authentication incomplete - waiting`);
            console.log(`[WA] ${tenantId}: Missing: ${!hasSockUser ? 'sock.user.id' : ''} ${!hasStateCreds ? 'state.creds.me.id' : ''}`);
            return;
          }
          
          s.authPaired = true;
          s.qrDataUrl = '';
          s.pushName = sock?.user?.name || sock?.user?.id || '';
          s.reconnectAttempts = 0;
          const phoneNumber = sock?.user?.id || 'unknown';
          
          console.log(`[WA] ${tenantId}: ✅ AUTHENTICATED! pushName=${s.pushName}, phone=${phoneNumber}`);
          
          // 🔥 FIX: When connection is established with authPaired=true, we CAN send messages
          // Previously canSend was only set to true after first successful send, creating a deadlock:
          // - Python blocks sends because canSend=false
          // - canSend never becomes true because no sends succeed
          // Now: if connected AND authPaired, set canSend=true immediately
          s.connected = true;
          s.starting = false;
          s.canSend = true;  // 🔥 FIX: Set to TRUE when authenticated - we can send!
          console.log(`[WA] ${tenantId}: 🎉 CONNECTED AND READY TO SEND! (connected=true, authPaired=true, canSend=true)`);
          
          // Resolve the starting promise
          if (resolvePromise) {
            resolvePromise(s);
          }
          
          qrLocks.delete(tenantId);
          console.log(`[WA] ${tenantId}: 🔓 QR lock released after successful pairing`);
          
          try { 
            if (fs.existsSync(qrFile)) {
              fs.unlinkSync(qrFile);
              console.log(`[WA] ${tenantId}: QR file deleted after connection`);
            }
          } catch(e) { 
            console.error(`[WA-ERROR] ${tenantId}: QR file delete error:`, e); 
          }
          
          notifyBackendWhatsappStatus(tenantId, 'connected', null);
        }
        
        if (connection === 'close') {
          s.connected = false;
          s.authPaired = false;
          s.starting = false;
          s.canSend = false;
          console.log(`[WA] ${tenantId}: ❌ Disconnected. reason=${reason}, message=${reasonMessage}`);
          
          qrLocks.delete(tenantId);
          
          // 🔥 CRITICAL: Always clean up socket before any reconnect
          try {
            if (s.sock) {
              s.sock.removeAllListeners();
              s.sock.end();
            }
          } catch (e) {
            console.log(`[WA] ${tenantId}: Socket cleanup warning: ${e.message}`);
          }
          
          // 🔥 CORRECTED: Determine disconnect type and handle appropriately
          const statusCode = lastDisconnect?.error?.output?.statusCode;
          const isLoggedOutEnum = reason === DisconnectReason.loggedOut;
          const isUnauthorized = statusCode === 401 || statusCode === 403;
          const isRealLogout = isLoggedOutEnum || isUnauthorized;
          
          console.log(`[WA-DIAGNOSTIC] ${tenantId}: Disconnect analysis: statusCode=${statusCode}, isLoggedOutEnum=${isLoggedOutEnum}, isUnauthorized=${isUnauthorized}, isRealLogout=${isRealLogout}`);
          
          // CASE 1: Real logged_out (401/403) - wipe auth and stop
          if (isRealLogout) {
            console.log(`[WA] ${tenantId}: 🔴 REAL LOGGED_OUT (statusCode=${statusCode}) - wipe auth, NO auto-restart`);
            
            notifyBackendWhatsappStatus(tenantId, 'disconnected', 'logged_out');
            
            // Wait for socket to fully close before deleting auth
            try {
              if (s.sock) {
                await new Promise(resolve => setTimeout(resolve, 500));
              }
            } catch (e) {
              console.log(`[WA] ${tenantId}: Socket wait warning: ${e.message}`);
            }
            
            // Delete auth files for real logout
            try {
              const authPath = authDir(tenantId);
              fs.rmSync(authPath, { recursive: true, force: true });
              console.log(`[WA] ${tenantId}: Auth files cleared for true logged_out`);
              fs.mkdirSync(authPath, { recursive: true });
            } catch (e) {
              console.error(`[WA-ERROR] ${tenantId}: Failed to clear auth files:`, e);
            }
            
            // Stop completely - require manual /start
            sessions.delete(tenantId);
            startingLocks.delete(tenantId);
            console.log(`[WA] ${tenantId}: Session cleared. User MUST manually scan QR via /start endpoint.`);
            
            if (rejectPromise) {
              rejectPromise(new Error('logged_out'));
            }
            return;
          }
          
          // CASE 2: Session replaced (440) - another device logged in
          if (statusCode === 440) {
            console.log(`[WA] ${tenantId}: 🔴 SESSION REPLACED (440) - stop, keep auth for potential recovery`);
            notifyBackendWhatsappStatus(tenantId, 'disconnected', 'session_replaced');
            sessions.delete(tenantId);
            startingLocks.delete(tenantId);
            console.log(`[WA] ${tenantId}: Session cleared. Manual QR scan required.`);
            
            if (rejectPromise) {
              rejectPromise(new Error('session_replaced'));
            }
            return;
          }
          
          // CASE 3: RestartRequired (515) - WhatsApp server explicitly requests restart
          // 🔥 FIX #5: Wrap in try-catch to prevent UNHANDLED exception
          if (reason === DisconnectReason.restartRequired) {
            try {
              console.log(`[WA] ${tenantId}: 🔄 RESTART_REQUIRED (515) - auto-reconnect with existing auth`);
              
              // Keep auth, auto-reconnect after short delay
              const attempts = (s.reconnectAttempts || 0) + 1;
              sessions.delete(tenantId);
              startingLocks.delete(tenantId);
              
              setTimeout(() => {
                console.log(`[${tenantId}] ⏰ Auto-reconnecting after restartRequired (attempt ${attempts})...`);
                getOrCreateSession(tenantId, 'restart_required').catch(err => {
                  console.error(`[WA-ERROR] ${tenantId}: restart_required reconnect failed:`, err.message);
                });
              }, 5000);
              
              if (rejectPromise) {
                rejectPromise(new Error('restart_required'));
              }
            } catch (restartError) {
              console.error(`[WA-ERROR] ${tenantId}: Error handling restart_required:`, restartError);
              if (rejectPromise) {
                rejectPromise(restartError);
              }
            }
            return;
          }
          
          // CASE 4: Other disconnects (network, timeout, etc) - auto-reconnect with backoff
          // These are temporary issues, keep auth and retry
          console.log(`[WA] ${tenantId}: 🔄 Temporary disconnect (statusCode=${statusCode}, reason=${reason}) - auto-reconnect with backoff`);
          
          const attempts = (s.reconnectAttempts || 0) + 1;
          
          if (attempts > RECONNECT_CONFIG.maxAttempts) {
            console.error(`[WA-ERROR] ${tenantId}: 🔴 Max reconnect attempts (${RECONNECT_CONFIG.maxAttempts}) reached`);
            console.error(`[WA-ERROR] ${tenantId}: Giving up. Manual /start required.`);
            notifyBackendWhatsappStatus(tenantId, 'disconnected', 'max_attempts_exceeded');
            sessions.delete(tenantId);
            startingLocks.delete(tenantId);
            
            if (rejectPromise) {
              rejectPromise(new Error('max_attempts_exceeded'));
            }
            return;
          }
          
          const delay = getReconnectDelay(attempts - 1);
          console.log(`[WA] ${tenantId}: Will auto-reconnect in ${delay/1000}s (attempt ${attempts}/${RECONNECT_CONFIG.maxAttempts}, keeping auth)`);
          
          // Store attempts count before deleting session
          const reconnectAttempts = attempts;
          sessions.delete(tenantId);
          startingLocks.delete(tenantId);
          
          setTimeout(() => {
            console.log(`[${tenantId}] ⏰ Auto-reconnecting after temporary disconnect (attempt ${reconnectAttempts})...`);
            getOrCreateSession(tenantId, 'auto_reconnect').then(newSession => {
              if (newSession) {
                newSession.reconnectAttempts = reconnectAttempts;
              }
            }).catch(err => {
              console.error(`[WA-ERROR] ${tenantId}: Auto-reconnect failed:`, err.message);
            });
          }, delay);
          
          if (rejectPromise) {
            rejectPromise(new Error(`disconnect_${statusCode || 'unknown'}`));
          }
        }
      } catch (e) { 
        console.error(`[WA-ERROR] ${tenantId}: connection.update error:`, e);
        if (rejectPromise) {
          rejectPromise(e);
        }
      }
    });

    sock.ev.on('messages.upsert', async (payload) => {
      try {
        const messages = payload.messages || [];
        
        console.log(`[${tenantId}] 🔔 ${messages.length} message(s) received, checking fromMe...`);
        
        // 🔥 LID FIX: Check for decryption errors in messages (Bad MAC, Failed to decrypt)
        // These errors occur in multi-device scenarios and should not crash the pipeline
        const validMessages = [];
        for (const msg of messages) {
          try {
            // Try to access message properties to trigger any decryption errors
            // This will throw if message can't be decrypted (Bad MAC, etc.)
            const _ = msg.key?.remoteJid && msg.message;
            
            validMessages.push(msg);
          } catch (decryptError) {
            // 🔥 LID FIX: Handle "Bad MAC" and "Failed to decrypt" errors gracefully
            const errorMsg = decryptError?.message || String(decryptError);
            if (errorMsg.includes('Bad MAC') || 
                errorMsg.includes('Failed to decrypt') || 
                errorMsg.includes('decrypt')) {
              const messageId = msg.key?.id || 'unknown';
              const remoteJid = msg.key?.remoteJid || 'unknown';
              console.warn(`[${tenantId}] ⚠️ Decrypt error for message ${messageId} from ${remoteJid.substring(0, 20)}: ${errorMsg}`);
              console.warn(`[${tenantId}] ⚠️ Skipping message due to decryption failure (multi-device sync issue)`);
              // Don't add to dedupe, don't send to Flask, don't crash - just skip
              continue;
            } else {
              // Re-throw unexpected errors
              throw decryptError;
            }
          }
        }
        
        if (validMessages.length < messages.length) {
          console.log(`[${tenantId}] ⚠️ Filtered out ${messages.length - validMessages.length} message(s) due to decryption errors`);
        }
        
        // 🔥 FIX #3: Extract LID and Android information from messages
        validMessages.forEach((msg, idx) => {
          const fromMe = msg.key?.fromMe;
          const remoteJid = msg.key?.remoteJid;
          const participant = msg.key?.participant;
          const pushName = msg.pushName || 'Unknown';
          
          // 🔥 FIX #3: Extract alternative JID (sender_pn) for proper reply routing
          const messageObj = msg.message || {};
          const senderKeyDistribution = messageObj.senderKeyDistributionMessage;
          const protocolMsg = messageObj.protocolMessage;
          
          // Try to find sender_pn from various message fields
          let senderPn = null;
          if (participant && participant.endsWith('@s.whatsapp.net')) {
            senderPn = participant;
          }
          
          console.log(`[${tenantId}] Message ${idx}: fromMe=${fromMe}, remoteJid=${remoteJid}, participant=${participant || 'N/A'}, pushName=${pushName}`);
          
          // 🔥 FIX #3: Log LID vs standard JID for debugging
          if (remoteJid.endsWith('@lid')) {
            console.log(`[${tenantId}] Message ${idx}: ⚠️ LID detected: ${remoteJid}, senderPn=${senderPn || 'N/A'}`);
          }
          
          const messageKeys = Object.keys(msg.message || {});
          console.log(`[${tenantId}] Message ${idx} content keys: ${messageKeys.join(', ')}`);
          
          const msgObj = msg.message || {};
          
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
          
          if (!msgObj.conversation && !msgObj.extendedTextMessage && !msgObj.imageMessage && 
              !msgObj.videoMessage && !msgObj.audioMessage && !msgObj.documentMessage) {
            console.log(`[${tenantId}] Message ${idx} UNKNOWN FORMAT - Full keys: ${messageKeys.join(', ')}`);
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
        
        const incomingMessages = validMessages.filter(msg => !msg.key.fromMe);
        
        if (incomingMessages.length > 0) {
          incomingMessages.forEach((msg, idx) => {
            const ourUserId = sock?.user?.id;
            const remoteJid = msg.key?.remoteJid;
            const fromMe = msg.key?.fromMe;
            const participant = msg.key?.participant;
            const pushName = msg.pushName;
            
            console.log(`[${tenantId}] 📨 Incoming ${idx}: remoteJid=${remoteJid}, fromMe=${fromMe}, participant=${participant || 'N/A'}, pushName=${pushName || 'N/A'}, ourUserId=${ourUserId}`);
          });
        }
        
        if (incomingMessages.length === 0) {
          console.log(`[${tenantId}] ⏭️ Skipping ${validMessages.length} outgoing message(s) (fromMe: true)`);
          return;
        }
        
        console.log(`[${tenantId}] 📨 ${incomingMessages.length} incoming message(s) detected - forwarding to Flask`);
        
        // 🔥 FIX: Improved deduplication - only by message_id + remoteJid, NO time window
        // This prevents dropping legitimate retry/ack events while still blocking true duplicates
        const newMessages = [];
        for (const msg of incomingMessages) {
          const messageId = msg.key?.id;
          const remoteJid = msg.key?.remoteJid;
          
          if (!messageId || !remoteJid) {
            console.log(`[${tenantId}] ⏭️ Skipping message with missing messageId or remoteJid`);
            continue;
          }
          
          // 🔥 FIX: Filter out non-message events (protocol messages, empty messages, etc.)
          const msgObj = msg.message || {};
          
          // Check for non-chat events that should be filtered
          if (msgObj.pollUpdateMessage) {
            console.log(`[${tenantId}] ⏭️ Skipping pollUpdateMessage ${messageId} - not a chat message`);
            continue;
          }
          if (msgObj.protocolMessage) {
            console.log(`[${tenantId}] ⏭️ Skipping protocolMessage ${messageId} - not a chat message`);
            continue;
          }
          if (msgObj.historySyncNotification) {
            console.log(`[${tenantId}] ⏭️ Skipping historySyncNotification ${messageId} - not a chat message`);
            continue;
          }
          
          // Check for actual text content
          if (!hasTextContent(msgObj)) {
            const msgKeys = Object.keys(msgObj);
            console.log(`[${tenantId}] ⏭️ Skipping non-message event ${messageId} - no text content, keys: ${msgKeys.join(',')}`);
            continue;
          }
          
          // Deduplication key: tenantId + remoteJid + messageId
          // This ensures we only process each unique message once per conversation
          const dedupKey = `${tenantId}:${remoteJid}:${messageId}`;
          
          if (messageDedup.has(dedupKey)) {
            console.log(`[${tenantId}] ⏭️ Skipping duplicate message ${messageId} from ${remoteJid.substring(0, 15)}`);
            continue;
          }
          
          messageDedup.set(dedupKey, Date.now());
          newMessages.push(msg);
          
          // Clean old dedup entries (keep last hour = DEDUP_CLEANUP_HOUR_MS)
          // This is sufficient to prevent duplicates while allowing memory cleanup
          if (messageDedup.size > DEDUP_MAX_SIZE) {
            const now = Date.now();
            for (const [key, timestamp] of messageDedup.entries()) {
              if (now - timestamp > DEDUP_CLEANUP_HOUR_MS) {
                messageDedup.delete(key);
              }
            }
          }
        }
        
        if (newMessages.length === 0) {
          console.log(`[${tenantId}] ⏭️ All messages were duplicates or non-message events - skipping webhook`);
          return;
        }
        
        // 🔥 LID FIX: Extract participant JID from all possible sources and attach metadata
        // 🔥 CRITICAL: For LID messages, resolve to phone number using internal endpoint
        for (const msg of newMessages) {
          const remoteJid = msg.key?.remoteJid || '';
          const messageId = msg.key?.id || '';
          const fromMe = msg.key?.fromMe || false;
          const extractedText = extractText(msg.message || {});
          const msgObj = msg.message || {};

          // Extract participant_jid from all possible locations
          let participantJid = msg.key?.participant
            || msg.participant
            || msgObj.extendedTextMessage?.contextInfo?.participant
            || msgObj.imageMessage?.contextInfo?.participant
            || msgObj.videoMessage?.contextInfo?.participant
            || msgObj.documentMessage?.contextInfo?.participant
            || msgObj.audioMessage?.contextInfo?.participant
            || msgObj.contactMessage?.contextInfo?.participant
            || null;

          // 🔥 NEW: If remoteJid is LID and no participant, try to resolve it
          let resolvedPhone = null;
          if (remoteJid.endsWith('@lid')) {
            try {
              console.log(`[${tenantId}] 🔍 LID detected, attempting phone resolution for ${remoteJid}...`);
              
              // Call internal /resolve-jid endpoint
              const resolveUrl = `http://localhost:${PORT}/internal/resolve-jid`;
              const resolveResponse = await axios.post(resolveUrl, {
                tenantId,
                jid: remoteJid,
                participant: participantJid,
                pushName: msg.pushName || null
              }, {
                headers: { 'X-Internal-Secret': INTERNAL_SECRET },
                timeout: 2000  // 2 second timeout for internal call
              });
              
              if (resolveResponse.data?.phone_e164) {
                resolvedPhone = resolveResponse.data.phone_e164;
                console.log(`[${tenantId}] ✅ LID resolved: ${remoteJid} → ${resolvedPhone}`);
              } else {
                console.log(`[${tenantId}] ⚠️ LID resolution returned no phone: ${JSON.stringify(resolveResponse.data)}`);
              }
            } catch (resolveError) {
              console.error(`[${tenantId}] ❌ LID resolution failed: ${resolveError.message}`);
            }
          }

          // Attach _lid_metadata so Flask can use it for phone resolution
          msg._lid_metadata = {
            remote_jid: remoteJid,
            participant_jid: participantJid || null,
            resolved_phone: resolvedPhone,  // 🔥 NEW: Include resolved phone
            push_name: msg.pushName || null
          };

          console.log(`[${tenantId}] 📤 Sending to Flask [${newMessages.indexOf(msg)}]: chat_jid=${remoteJid}, message_id=${messageId}, from_me=${fromMe}, participant_jid=${participantJid || 'N/A'}, resolved_phone=${resolvedPhone || 'N/A'}, text=${(extractedText || '').substring(0, 50)}...`);

          // Highlight LID messages
          if (remoteJid.endsWith('@lid')) {
            console.log(`[${tenantId}] [WA-LID] lid=${remoteJid}, participant=${participantJid || 'none'}, resolved_phone=${resolvedPhone || 'FAILED'}, push_name=${msg.pushName || 'none'}`);
          }
        }
        
        const filteredPayload = {
          ...payload,
          messages: newMessages
        };
        
        // 🔥 FIX: Include tenantId in the payload structure expected by Flask
        const webhookPayload = {
          tenantId,
          payload: filteredPayload
        };
        
        // 🔥 FIX #1: Wrap webhook call with fail-safe and queue
        try {
          const response = await axios.post(`${FLASK_BASE_URL}/api/whatsapp/webhook/incoming`,
            webhookPayload,
            { 
              headers: { 
                'Content-Type': 'application/json',
                'X-Internal-Secret': INTERNAL_SECRET 
              },
              timeout: 30000  // 30 second timeout - increased for slow Flask processing
            }
          );
          console.log(`[${tenantId}] ✅ Webhook→Flask success:`, response.status);
        } catch (e) {
          console.error(`[${tenantId}] ❌ [Webhook→Flask] failed:`, e?.code || e?.message || e);
          
          // 🔥 FIX #1: Log DNS errors clearly
          if (e?.code === 'EAI_AGAIN' || e?.code === 'ENOTFOUND') {
            console.error(`[${tenantId}] 🔴 DNS ERROR: Cannot resolve ${FLASK_BASE_URL}`);
            console.error(`[${tenantId}] 🔴 Check FLASK_BASE_URL/BACKEND_BASE_URL environment variable`);
          }
          
          if (e.response) {
            console.error(`[${tenantId}] Flask response:`, e.response.status, e.response.data);
          }
          
          // 🔥 FIX #1: Queue messages for retry if backend is down or rate limited
          // Include 429 (rate limit) and 503 (service unavailable) for retry
          if (e?.code === 'EAI_AGAIN' || e?.code === 'ENOTFOUND' || e?.code === 'ECONNREFUSED' || 
              e?.code === 'ETIMEDOUT' || 
              (e.response && (e.response.status >= 500 || e.response.status === 429))) {
            
            // Add to retry queue
            for (const msg of newMessages) {
              const messageId = msg.key?.id;
              if (!messageId) continue;
              
              if (messageQueue.length < MAX_QUEUE_SIZE) {
                // Store the remoteJid for proper dedup key reconstruction
                const msgRemoteJid = msg.key?.remoteJid || '';
                
                messageQueue.push({
                  tenantId,
                  messageId,
                  remoteJid: msgRemoteJid,  // Store for dedup key reconstruction
                  payload: {
                    tenantId,
                    payload: { ...payload, messages: [msg] }  // Use correct webhook structure
                  },
                  attempts: 0,
                  lastAttempt: Date.now(),
                  createdAt: Date.now()
                });
                console.log(`[${tenantId}] 📝 Message ${messageId} queued for retry (queue size: ${messageQueue.length})`);
              } else {
                console.error(`[${tenantId}] ❌ Message queue full (${MAX_QUEUE_SIZE}) - dropping message ${messageId}`);
              }
            }
          }
        }
      } catch (e) { 
        console.error(`[${tenantId}] ❌ [messages.upsert] handler error:`, e?.message || e);
      }
    });

    // 🔥 ANDROID FIX: Release starting lock when session fully initialized
    // Do this AFTER all event handlers are registered
    startingLocks.delete(tenantId);
    console.log(`[${tenantId}] 🔓 Released starting lock - session initialized`);

    return s;
  } catch (error) {
    // Clean up on error
    console.error(`[${tenantId}] ❌ startSession failed:`, error);
    sessions.delete(tenantId);
    startingLocks.delete(tenantId);
    qrLocks.delete(tenantId);
    
    if (rejectPromise) {
      rejectPromise(error);
    }
    throw error;
  }
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
async function start() {
  if (server) return server;
  
  // 🔥 FIX #1: Wait for backend before starting webhook processing
  await waitForBackendReady();
  
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