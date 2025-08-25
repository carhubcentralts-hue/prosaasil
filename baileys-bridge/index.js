import express from "express";
import makeWASocket, { useMultiFileAuthState, DisconnectReason } from "@whiskeysockets/baileys";
import Pino from "pino";
import qrcode from "qrcode-terminal";

const app = express();
app.use(express.json({limit:"1mb"}));

const PORT = process.env.BAILEYS_PORT || 4001;
const WEBHOOK = process.env.BAILEYS_WEBHOOK || "http://127.0.0.1:5000/webhook/whatsapp/baileys";
const SECRET = process.env.BAILEYS_SECRET || "";

console.log(`🚀 Starting Baileys bridge on port ${PORT}`);
console.log(`📡 Webhook URL: ${WEBHOOK}`);

const logger = Pino({ level: "info" });
let sock = null;

async function initSocket() {
    try {
        const { state, saveCreds } = await useMultiFileAuthState("./auth");
        
        sock = makeWASocket({ 
            auth: state, 
            printQRInTerminal: true, 
            logger 
        });

        sock.ev.on("creds.update", saveCreds);
        
        sock.ev.on("connection.update", (update) => {
            const { connection, lastDisconnect, qr } = update;
            
            if (qr) {
                console.log("📱 QR Code generated, scan with WhatsApp");
                qrcode.generate(qr, { small: true });
            }
            
            if (connection === 'close') {
                const shouldReconnect = (lastDisconnect?.error)?.output?.statusCode !== DisconnectReason.loggedOut;
                console.log('Connection closed due to ', lastDisconnect?.error, ', reconnecting ', shouldReconnect);
                if (shouldReconnect) {
                    setTimeout(initSocket, 5000);
                }
            } else if (connection === 'open') {
                console.log('✅ Baileys connected successfully');
            }
        });

        sock.ev.on("messages.upsert", async (m) => {
            try {
                const msg = m.messages?.[0];
                if (!msg || !WEBHOOK || msg.key.fromMe) return;
                
                const from = msg.key.remoteJid;
                const text = msg.message?.conversation
                          || msg.message?.extendedTextMessage?.text
                          || "";
                
                if (!text) return;
                
                console.log(`📩 Incoming message from ${from}: ${text.substring(0, 50)}...`);
                
                await fetch(WEBHOOK, {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json", 
                        "X-BAILEYS-SECRET": SECRET 
                    },
                    body: JSON.stringify({ 
                        from, 
                        text, 
                        provider: "baileys",
                        message_id: msg.key.id,
                        timestamp: msg.messageTimestamp
                    })
                });
                
                console.log("✅ Message forwarded to webhook");
                
            } catch(e) { 
                console.error("❌ Webhook forward error:", e); 
            }
        });
        
    } catch (error) {
        console.error("❌ Socket initialization error:", error);
        setTimeout(initSocket, 10000);
    }
}

// API endpoint for sending messages
app.post("/sendMessage", async (req, res) => {
    try {
        const { to, text } = req.body || {};
        
        if (!to || !text) {
            return res.status(400).json({ ok: false, error: "Missing to/text" });
        }
        
        if (!sock) {
            return res.status(500).json({ ok: false, error: "Socket not connected" });
        }
        
        // Clean WhatsApp JID format
        const jid = to.replace(/^whatsapp:/, "").replace(/[^\d]/g, "") + "@s.whatsapp.net";
        
        console.log(`📤 Sending message to ${jid}: ${text.substring(0, 50)}...`);
        
        const response = await sock.sendMessage(jid, { text });
        
        console.log("✅ Message sent successfully");
        
        return res.json({ 
            ok: true, 
            result: response,
            message_id: response.key?.id 
        });
        
    } catch(e) { 
        console.error("❌ Send message error:", e); 
        res.status(500).json({ ok: false, error: String(e) }); 
    }
});

// Health check
app.get("/health", (req, res) => {
    res.json({ 
        ok: true, 
        connected: !!sock,
        timestamp: new Date().toISOString()
    });
});

// Start server
app.listen(PORT, () => {
    console.log(`🌐 Baileys HTTP bridge listening on port ${PORT}`);
    initSocket();
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('🛑 Shutting down Baileys bridge...');
    if (sock) {
        sock.logout();
    }
    process.exit(0);
});
