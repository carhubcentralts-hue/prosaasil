// services/whatsapp/baileys_service.js
const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const fs = require('fs');
const path = require('path');
const axios = require('axios');

const app = express();
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// Environment validation
const requiredEnvVars = ['INTERNAL_SECRET', 'FLASK_BASE_URL'];
const missingEnvVars = requiredEnvVars.filter(envVar => !process.env[envVar]);
if (missingEnvVars.length > 0) {
  console.error(`❌ Missing required environment variables: ${missingEnvVars.join(', ')}`);
  process.exit(1);
}

const PORT = process.env.BAILEYS_PORT || 3001;
const INTERNAL_SECRET = process.env.INTERNAL_SECRET;
const FLASK_BASE_URL = process.env.FLASK_BASE_URL;

// Security: Strong tenant ID validation (prevent path traversal)
const TENANT_ID_REGEX = /^[A-Za-z0-9_-]{1,64}$/;
function validateTenantId(tenantId) {
  if (!tenantId || typeof tenantId !== 'string') {
    throw new Error('Invalid tenant ID: must be a non-empty string');
  }
  if (!TENANT_ID_REGEX.test(tenantId)) {
    throw new Error('Invalid tenant ID: must contain only alphanumeric characters, hyphens, and underscores (1-64 chars)');
  }
  return tenantId;
}

const sessions = new Map(); // tenantId -> { sock, state, qrDataUrl, connected, pushName }

function authDir(tenantId) {
  // Security: Validate tenant ID and ensure path stays within storage/whatsapp
  validateTenantId(tenantId);
  const storageRoot = path.join(process.cwd(), 'storage', 'whatsapp');
  const authPath = path.join(storageRoot, tenantId, 'auth');
  
  // Double-check that the resolved path is within our storage directory
  if (!authPath.startsWith(storageRoot)) {
    throw new Error('Path traversal attempt detected');
  }
  
  return authPath;
}

async function startSession(tenantId) {
  validateTenantId(tenantId);
  if (sessions.get(tenantId)?.sock) return sessions.get(tenantId);

  fs.mkdirSync(authDir(tenantId), { recursive: true });
  const { state, saveCreds } = await useMultiFileAuthState(authDir(tenantId));

  const sock = makeWASocket({ 
    auth: state, 
    printQRInTerminal: false,
    browser: ['Shai CRM', 'Chrome', '120']
  });
  
  const session = { sock, state, saveCreds, qrDataUrl: '', connected: false, pushName: '' };
  sessions.set(tenantId, session);

  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      try {
        session.qrDataUrl = await QRCode.toDataURL(qr);
        console.log(`🔄 QR updated for tenant ${tenantId}`);
      } catch (error) {
        console.error(`❌ QR generation failed for tenant ${tenantId}:`, error);
      }
    }

    if (connection === 'open') {
      session.connected = true;
      session.pushName = sock?.user?.name || sock?.user?.id || '';
      session.qrDataUrl = '';
      console.log(`✅ WhatsApp connected for tenant ${tenantId} as ${session.pushName}`);
    }
    if (connection === 'close') {
      session.connected = false;
      const shouldReconnect = (lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut);
      if (shouldReconnect) {
        console.log(`🔄 Reconnecting tenant ${tenantId} after disconnect...`);
        setTimeout(() => startSession(tenantId), 2000);
      } else {
        console.log(`🚪 Tenant ${tenantId} logged out`);
      }
    }
  });

  // הודעות נכנסות → שלח ל-Flask Webhook
  sock.ev.on('messages.upsert', async (m) => {
    try {
      const messages = m.messages || [];
      for (const message of messages) {
        // Skip outgoing messages (fromMe = true)
        if (message.key && message.key.fromMe) {
          continue;
        }
        
        // Extract message data properly
        const from = message.key.remoteJid;
        const messageId = message.key.id;
        const timestamp = message.messageTimestamp;
        
        // Extract text content based on message type
        let text = '';
        let messageType = 'text';
        
        if (message.message?.conversation) {
          text = message.message.conversation;
        } else if (message.message?.extendedTextMessage?.text) {
          text = message.message.extendedTextMessage.text;
        } else if (message.message?.imageMessage?.caption) {
          text = message.message.imageMessage.caption;
          messageType = 'image';
        } else if (message.message?.videoMessage?.caption) {
          text = message.message.videoMessage.caption;
          messageType = 'video';
        } else if (message.message?.documentMessage?.caption) {
          text = message.message.documentMessage.caption;
          messageType = 'document';
        }
        
        // Skip if no text content
        if (!text || text.trim() === '') {
          console.log(`⏩ Skipping message with no text content from ${from}`);
          continue;
        }
        
        console.log(`📨 Inbound WhatsApp from ${from} for tenant ${tenantId}: "${text.substring(0, 50)}..."`);
        
        // Forward to Flask webhook with proper structure
        await axios.post(`${FLASK_BASE_URL}/api/whatsapp/webhook/incoming`, {
          tenantId,
          from,
          text,
          messageId,
          type: messageType,
          timestamp
        }, {
          headers: { 
            'Content-Type': 'application/json', 
            'X-Internal-Secret': INTERNAL_SECRET 
          },
          timeout: 5000
        });
      }
    } catch (e) { 
      console.error(`❌ Failed to forward message for tenant ${tenantId}:`, e.message);
    }
  });

  return session;
}

function requireSecret(req, res, next) {
  if (req.header('X-Internal-Secret') !== INTERNAL_SECRET) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  next();
}

// Health check endpoint
app.get('/healthz', (req, res) => res.status(200).send('ok'));

// Start session for tenant
app.post('/whatsapp/:tenantId/start', requireSecret, async (req, res) => {
  const { tenantId } = req.params;
  try {
    validateTenantId(tenantId);
    await startSession(tenantId);
    res.json({ ok: true, message: `Session started for tenant ${tenantId}` });
  } catch (error) {
    console.error(`❌ Failed to start session for tenant ${tenantId}:`, error);
    if (error.message.includes('Invalid tenant ID') || error.message.includes('Path traversal')) {
      res.status(400).json({ error: 'invalid_tenant_id', message: error.message });
    } else {
      res.status(500).json({ error: 'failed_to_start', message: error.message });
    }
  }
});

// Get session status
app.get('/whatsapp/:tenantId/status', requireSecret, (req, res) => {
  const { tenantId } = req.params;
  try {
    validateTenantId(tenantId);
    const s = sessions.get(tenantId);
    res.json({ 
      connected: !!s?.connected, 
      pushName: s?.pushName || '', 
      hasQR: !!s?.qrDataUrl 
    });
  } catch (error) {
    res.status(400).json({ error: 'invalid_tenant_id', message: error.message });
  }
});

// Get QR code
app.get('/whatsapp/:tenantId/qr', requireSecret, (req, res) => {
  const { tenantId } = req.params;
  try {
    validateTenantId(tenantId);
    const s = sessions.get(tenantId);
    if (s?.qrDataUrl) {
      return res.json({ dataUrl: s.qrDataUrl });
    }
    return res.status(404).json({ error: 'no qr' });
  } catch (error) {
    res.status(400).json({ error: 'invalid_tenant_id', message: error.message });
  }
});

// Send message
app.post('/whatsapp/:tenantId/send', requireSecret, async (req, res) => {
  const { tenantId } = req.params;
  const { to, text } = req.body;
  
  try {
    validateTenantId(tenantId);
    
    if (!to || !text) {
      return res.status(400).json({ error: 'to and text are required' });
    }
    
    const s = sessions.get(tenantId);
    if (!s?.connected) {
      return res.status(503).json({ error: 'not_connected' });
    }
    
    const jid = to.endsWith('@s.whatsapp.net') ? to : to.replace(/[^\d]/g, '') + '@s.whatsapp.net';
    await s.sock.sendMessage(jid, { text });
    res.json({ ok: true, message: 'Message sent' });
  } catch (error) {
    console.error(`❌ Failed to send message for tenant ${tenantId}:`, error);
    if (error.message.includes('Invalid tenant ID')) {
      res.status(400).json({ error: 'invalid_tenant_id', message: error.message });
    } else {
      res.status(500).json({ error: 'send_failed', message: error.message });
    }
  }
});

// Logout session
app.post('/whatsapp/:tenantId/logout', requireSecret, async (req, res) => {
  const { tenantId } = req.params;
  
  try {
    validateTenantId(tenantId);
    const s = sessions.get(tenantId);
    
    if (s?.sock?.logout) {
      await s.sock.logout();
    }
    sessions.delete(tenantId);
    
    // Clean up auth directory
    const authPath = authDir(tenantId);
    if (fs.existsSync(authPath)) {
      fs.rmSync(authPath, { recursive: true, force: true });
    }
    
    res.json({ ok: true, message: `Session logged out for tenant ${tenantId}` });
  } catch (error) {
    console.error(`❌ Failed to logout tenant ${tenantId}:`, error);
    if (error.message.includes('Invalid tenant ID') || error.message.includes('Path traversal')) {
      res.status(400).json({ error: 'invalid_tenant_id', message: error.message });
    } else {
      res.status(500).json({ error: 'logout_failed', message: error.message });
    }
  }
});

app.listen(PORT, () => {
  console.log(`🚀 Baileys Multi-Tenant Service running on port ${PORT}`);
  console.log(`📁 Auth storage: storage/whatsapp/*/auth/`);
  console.log(`🔐 Internal secret: ${INTERNAL_SECRET ? 'Configured' : 'MISSING'}`);
});

// Graceful shutdown with proper cleanup
async function gracefulShutdown(signal) {
  console.log(`🛑 Received ${signal}. Shutting down Baileys service gracefully...`);
  
  try {
    // Close all active sessions
    for (const [tenantId, session] of sessions.entries()) {
      try {
        console.log(`📱 Closing session for tenant: ${tenantId}`);
        if (session.sock && session.sock.end) {
          await session.sock.end();
        }
      } catch (error) {
        console.error(`❌ Error closing session for ${tenantId}:`, error.message);
      }
    }
    
    console.log('✅ All sessions closed successfully');
  } catch (error) {
    console.error('❌ Error during graceful shutdown:', error);
  } finally {
    process.exit(0);
  }
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// Error handling
process.on('uncaughtException', (err) => {
  console.error('❌ Uncaught Exception:', err);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('❌ Unhandled Rejection at:', promise, 'reason:', reason);
});