/**
 * Baileys WhatsApp Bridge for AgentLocator
 * Listens on local port, communicates with Python via webhooks
 */
import express from 'express';
import { Boom } from '@hapi/boom';
import makeWASocket, { 
    DisconnectReason, 
    useMultiFileAuthState, 
    fetchLatestBaileysVersion 
} from '@adiwajshing/baileys';
import pino from 'pino';
import fetch from 'node-fetch';
import crypto from 'crypto';

const app = express();
app.use(express.json());

const logger = pino({ 
    level: process.env.LOG_LEVEL || 'info',
    transport: { target: 'pino-pretty', options: { colorize: true } }
});

let sock = null;
let connectionStatus = 'disconnected';

// Environment configuration
const PORT = process.env.WA_BAILEYS_PORT || 8000;
const SESSION_DIR = process.env.WA_SESSION_DIR || './session';
const PYTHON_WEBHOOK_URL = process.env.PYTHON_WEBHOOK_URL || 'http://127.0.0.1:5000/webhook/whatsapp/baileys';
const SHARED_SECRET = process.env.WA_SHARED_SECRET || '';

// Health endpoint
app.get('/healthz', (req, res) => {
    res.json({
        status: 'ok',
        connected: connectionStatus === 'connected',
        timestamp: new Date().toISOString()
    });
});

// Send message endpoint
app.post('/send', async (req, res) => {
    try {
        const { to, text, media_url } = req.body;
        
        if (!to) {
            return res.status(400).json({ error: 'to field is required' });
        }
        
        if (!sock || connectionStatus !== 'connected') {
            return res.status(503).json({ error: 'WhatsApp not connected' });
        }
        
        // Format phone number for Baileys
        const jid = to.includes('@') ? to : `${to}@s.whatsapp.net`;
        
        let message = {};
        if (media_url) {
            // Media message
            const mediaResponse = await fetch(media_url);
            const mediaBuffer = await mediaResponse.buffer();
            message = {
                image: mediaBuffer,
                caption: text || ''
            };
        } else if (text) {
            // Text message
            message = { text };
        } else {
            return res.status(400).json({ error: 'Either text or media_url is required' });
        }
        
        const result = await sock.sendMessage(jid, message);
        const messageId = result.key.id;
        
        logger.info(`Message sent to ${to}: ${messageId}`);
        
        res.json({
            ok: true,
            message_id: messageId,
            to: jid
        });
        
    } catch (error) {
        logger.error(`Send message error: ${error.message}`);
        res.status(500).json({ 
            error: 'Failed to send message',
            details: error.message 
        });
    }
});

// Initialize WhatsApp connection
async function startWhatsApp() {
    try {
        const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
        const { version } = await fetchLatestBaileysVersion();
        
        sock = makeWASocket({
            version,
            logger: logger.child({ module: 'baileys' }),
            printQRInTerminal: true,
            auth: state,
            generateHighQualityLinkPreview: true,
        });
        
        sock.ev.on('connection.update', (update) => {
            const { connection, lastDisconnect, qr } = update;
            
            if (qr) {
                logger.info('QR Code generated - scan with WhatsApp');
            }
            
            if (connection === 'close') {
                const shouldReconnect = (lastDisconnect?.error instanceof Boom) 
                    && lastDisconnect.error.output.statusCode !== DisconnectReason.loggedOut;
                    
                logger.info('Connection closed, reconnecting:', shouldReconnect);
                connectionStatus = 'disconnected';
                
                if (shouldReconnect) {
                    setTimeout(startWhatsApp, 5000);
                }
            } else if (connection === 'open') {
                logger.info('WhatsApp connection established successfully');
                connectionStatus = 'connected';
            }
        });
        
        sock.ev.on('creds.update', saveCreds);
        
        // Handle incoming messages
        sock.ev.on('messages.upsert', async ({ messages }) => {
            for (const msg of messages) {
                if (msg.key.fromMe || !msg.message) continue;
                
                try {
                    await handleIncomingMessage(msg);
                } catch (error) {
                    logger.error(`Error handling message: ${error.message}`);
                }
            }
        });
        
    } catch (error) {
        logger.error(`WhatsApp initialization error: ${error.message}`);
        setTimeout(startWhatsApp, 10000);
    }
}

// Handle incoming message and forward to Python
async function handleIncomingMessage(msg) {
    try {
        const from = msg.key.remoteJid;
        let text = '';
        let media_url = null;
        
        // Extract message content
        if (msg.message.conversation) {
            text = msg.message.conversation;
        } else if (msg.message.extendedTextMessage) {
            text = msg.message.extendedTextMessage.text;
        } else if (msg.message.imageMessage) {
            text = msg.message.imageMessage.caption || '';
            // Note: In production, you'd download and host the media
            media_url = 'https://placeholder.com/media';
        }
        
        const payload = {
            from: from.replace('@s.whatsapp.net', ''),
            text,
            media_url,
            provider_msg_id: msg.key.id,
            timestamp: new Date().toISOString()
        };
        
        // Sign the payload with HMAC
        const signature = crypto
            .createHmac('sha256', SHARED_SECRET)
            .update(JSON.stringify(payload))
            .digest('hex');
        
        // Forward to Python webhook
        const response = await fetch(PYTHON_WEBHOOK_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-BAILEYS-SIGNATURE': signature
            },
            body: JSON.stringify(payload),
            timeout: 5000
        });
        
        if (!response.ok) {
            throw new Error(`Python webhook returned ${response.status}`);
        }
        
        logger.info(`Forwarded message from ${from} to Python`);
        
    } catch (error) {
        logger.error(`Error forwarding message to Python: ${error.message}`);
    }
}

// Start the bridge
app.listen(PORT, '127.0.0.1', () => {
    logger.info(`Baileys bridge listening on http://127.0.0.1:${PORT}`);
    startWhatsApp();
});

// Graceful shutdown
process.on('SIGTERM', () => {
    logger.info('Received SIGTERM, shutting down gracefully');
    if (sock) {
        sock.ws.close();
    }
    process.exit(0);
});