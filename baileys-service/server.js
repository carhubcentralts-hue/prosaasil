/**
 * Baileys WhatsApp Service for AgentLocator CRM
 * Handles session management, message sending, and webhook responses
 */
import express from 'express';
import makeWASocket, { 
  DisconnectReason, 
  useMultiFileAuthState, 
  fetchLatestBaileysVersion 
} from '@whiskeysockets/baileys';
import qrTerminal from 'qrcode-terminal';
import NodeCache from 'node-cache';
import crypto from 'crypto';

const app = express();
const PORT = process.env.PORT || 3001;
const WEBHOOK_SECRET = process.env.BAILEYS_WEBHOOK_SECRET || '';
const BAILEYS_WEBHOOK_TARGET = process.env.PUBLIC_BASE_URL ? 
  `${process.env.PUBLIC_BASE_URL}/webhook/whatsapp/baileys` : null;

// Validate required environment variables
if (!WEBHOOK_SECRET) {
  console.error('FATAL: BAILEYS_WEBHOOK_SECRET is required for security');
  process.exit(1);
}

if (!BAILEYS_WEBHOOK_TARGET) {
  console.error('WARNING: PUBLIC_BASE_URL not set - webhook forwarding disabled');
}

console.log('Baileys service configuration:');
console.log('- Port:', PORT);
console.log('- Webhook target:', BAILEYS_WEBHOOK_TARGET || 'DISABLED');
console.log('- Security enabled:', !!WEBHOOK_SECRET);

// Middleware
app.use(express.json());

// Cache for idempotency and deduplication
const messageCache = new NodeCache({ stdTTL: 3600 }); // 1 hour cache
const sentMessages = new NodeCache({ stdTTL: 86400 }); // 24 hour dedup

// Global state
let sock;
let qrCode = '';
let connectionState = 'disconnected';
let lastConnectionTime = null;

/**
 * Initialize WhatsApp connection with session management
 */
async function initializeWhatsApp() {
  try {
    const { state, saveCreds } = await useMultiFileAuthState('./auth_info_baileys');
    const { version, isLatest } = await fetchLatestBaileysVersion();

    console.log(`Using WA v${version.join('.')}, isLatest: ${isLatest}`);

    sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: true,
      browser: ['AgentLocator CRM', 'Chrome', '1.0.0'],
      defaultQueryTimeoutMs: 60000,
      connectTimeoutMs: 60000,
      keepAliveIntervalMs: 30000,
    });

    // Connection state management
    sock.ev.on('connection.update', (update) => {
      const { connection, lastDisconnect, qr } = update;
      
      if (qr) {
        qrCode = qr;
        qrTerminal.generate(qr, { small: true });
        console.log('QR Code generated. Scan with WhatsApp.');
      }

      if (connection === 'close') {
        const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
        console.log('Connection closed. Reconnecting:', shouldReconnect);
        
        connectionState = 'disconnected';
        
        if (shouldReconnect) {
          setTimeout(() => {
            console.log('Attempting to reconnect...');
            initializeWhatsApp();
          }, 5000);
        }
      } else if (connection === 'open') {
        console.log('WhatsApp connection established successfully!');
        connectionState = 'connected';
        lastConnectionTime = new Date();
        qrCode = '';
      } else {
        connectionState = connection || 'unknown';
      }
    });

    // Save credentials on update
    sock.ev.on('creds.update', saveCreds);

    // Message handler for incoming messages
    sock.ev.on('messages.upsert', async (messageUpdate) => {
      const messages = messageUpdate.messages;
      
      for (const message of messages) {
        if (!message.key.fromMe && message.message) {
          await handleIncomingMessage(message);
        }
      }
    });

  } catch (error) {
    console.error('Failed to initialize WhatsApp:', error);
    connectionState = 'error';
    
    // Retry after 10 seconds
    setTimeout(() => {
      console.log('Retrying WhatsApp initialization...');
      initializeWhatsApp();
    }, 10000);
  }
}

/**
 * Handle incoming WhatsApp messages and forward to Python backend
 */
async function handleIncomingMessage(message) {
  try {
    const from = message.key.remoteJid;
    const messageId = message.key.id;
    const timestamp = message.messageTimestamp;
    
    // Extract message content
    let body = '';
    let messageType = 'text';
    let mediaUrl = '';
    
    if (message.message?.conversation) {
      body = message.message.conversation;
    } else if (message.message?.extendedTextMessage?.text) {
      body = message.message.extendedTextMessage.text;
    } else if (message.message?.imageMessage) {
      messageType = 'image';
      body = message.message.imageMessage.caption || '';
      // Note: Media URL extraction would require additional handling
    } else if (message.message?.documentMessage) {
      messageType = 'document';
      body = message.message.documentMessage.caption || '';
    }

    // Deduplication check
    const dedupKey = `${from}_${messageId}`;
    if (sentMessages.has(dedupKey)) {
      console.log(`Duplicate message ignored: ${messageId}`);
      return;
    }
    sentMessages.set(dedupKey, true);

    console.log(`Incoming message from ${from}: ${body.substring(0, 50)}...`);

    // Forward to Python webhook if configured
    if (BAILEYS_WEBHOOK_TARGET && WEBHOOK_SECRET) {
      const payload = {
        from: from.replace('@c.us', ''),
        body,
        id: messageId,
        type: messageType,
        mediaUrl,
        timestamp
      };

      const signature = crypto
        .createHmac('sha256', WEBHOOK_SECRET)
        .update(JSON.stringify(payload))
        .digest('hex');

      try {
        const response = await fetch(BAILEYS_WEBHOOK_TARGET, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-BAILEYS-SECRET': WEBHOOK_SECRET
          },
          body: JSON.stringify(payload)
        });

        if (response.ok) {
          console.log(`Message forwarded to Python webhook: ${messageId}`);
        } else {
          console.error(`Webhook forward failed: ${response.status} ${response.statusText}`);
        }
      } catch (error) {
        console.error('Error forwarding to webhook:', error);
      }
    }

  } catch (error) {
    console.error('Error handling incoming message:', error);
  }
}

/**
 * Send WhatsApp message with idempotency
 */
async function sendWhatsAppMessage(to, type, content, idempotencyKey) {
  if (!sock || connectionState !== 'connected') {
    throw new Error('WhatsApp not connected');
  }

  // Idempotency check
  if (idempotencyKey && messageCache.has(idempotencyKey)) {
    const cached = messageCache.get(idempotencyKey);
    console.log(`Returning cached result for ${idempotencyKey}`);
    return cached;
  }

  // Format phone number
  const jid = to.includes('@') ? to : `${to}@c.us`;
  
  let result;
  
  try {
    if (type === 'text') {
      result = await sock.sendMessage(jid, { text: content.text });
    } else if (type === 'media' && content.mediaUrl) {
      if (content.mediaUrl.match(/\.(jpg|jpeg|png|gif)$/i)) {
        result = await sock.sendMessage(jid, { 
          image: { url: content.mediaUrl },
          caption: content.caption || ''
        });
      } else {
        result = await sock.sendMessage(jid, { 
          document: { url: content.mediaUrl },
          mimetype: 'application/octet-stream',
          fileName: 'document'
        });
      }
    } else {
      throw new Error(`Unsupported message type: ${type}`);
    }

    const response = {
      success: true,
      messageId: result.key.id,
      timestamp: result.messageTimestamp,
      to: jid
    };

    // Cache result if idempotency key provided
    if (idempotencyKey) {
      messageCache.set(idempotencyKey, response);
    }

    console.log(`Message sent to ${to}: ${result.key.id}`);
    return response;

  } catch (error) {
    console.error(`Failed to send message to ${to}:`, error);
    throw error;
  }
}

// API Routes

/**
 * Enhanced health check endpoint with detailed status
 */
app.get('/health', (req, res) => {
  const health = {
    status: connectionState === 'connected' ? 'ok' : 'degraded',
    connection: connectionState,
    connected: connectionState === 'connected',
    ready: connectionState === 'connected' && !!sock,
    lastConnected: lastConnectionTime,
    uptime: process.uptime(),
    qrAvailable: !!qrCode,
    timestamp: new Date().toISOString()
  };
  
  // Set appropriate HTTP status
  const httpStatus = health.connected ? 200 : 503;
  res.status(httpStatus).json(health);
});

/**
 * Get QR code for authentication
 */
app.get('/qr', (req, res) => {
  if (qrCode) {
    res.json({
      success: true,
      qrCode,
      message: 'Scan this QR code with WhatsApp'
    });
  } else if (connectionState === 'connected') {
    res.json({
      success: true,
      message: 'Already connected to WhatsApp'
    });
  } else {
    res.json({
      success: false,
      message: 'QR code not available. Check connection status.'
    });
  }
});

/**
 * Send message endpoint
 */
app.post('/send', async (req, res) => {
  try {
    const { to, type = 'text', text, mediaUrl, caption, idempotencyKey, webhook_response } = req.body;

    if (!to) {
      return res.status(400).json({
        success: false,
        error: 'Phone number (to) is required'
      });
    }

    // Prevent webhook loops
    if (webhook_response) {
      console.log(`Webhook response message to ${to} - processing normally`);
    }

    // Prepare content based on type
    const content = {};
    if (type === 'text') {
      if (!text) {
        return res.status(400).json({
          success: false,
          error: 'Text content is required for text messages'
        });
      }
      content.text = text;
    } else if (type === 'media') {
      if (!mediaUrl) {
        return res.status(400).json({
          success: false,
          error: 'Media URL is required for media messages'
        });
      }
      content.mediaUrl = mediaUrl;
      content.caption = caption || '';
    }

    const result = await sendWhatsAppMessage(to, type, content, idempotencyKey);
    
    // Cache successful send for deduplication
    if (result.messageId && idempotencyKey) {
      sentMessages.set(idempotencyKey, {
        messageId: result.messageId,
        timestamp: Date.now(),
        to: to
      });
    }
    
    res.json({
      success: true,
      ...result
    });

  } catch (error) {
    console.error('Send message error:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

/**
 * Get connection status
 */
app.get('/status', (req, res) => {
  res.json({
    connected: connectionState === 'connected',
    state: connectionState,
    lastConnected: lastConnectionTime,
    uptime: process.uptime(),
    messagesCached: messageCache.keys().length,
    messagesDeduped: sentMessages.keys().length
  });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Express error:', err);
  res.status(500).json({
    success: false,
    error: 'Internal server error'
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: 'Endpoint not found'
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`Baileys WhatsApp Service running on port ${PORT}`);
  console.log('Environment:', {
    webhookUrl: PYTHON_WEBHOOK_URL,
    hasWebhookSecret: !!WEBHOOK_SECRET,
    port: PORT
  });
  
  // Initialize WhatsApp connection
  initializeWhatsApp();
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('Shutting down gracefully...');
  if (sock) {
    sock.end();
  }
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('Received SIGTERM, shutting down...');
  if (sock) {
    sock.end();
  }
  process.exit(0);
});