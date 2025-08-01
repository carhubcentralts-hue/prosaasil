const { default: makeWASocket, DisconnectReason, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const fs = require('fs');
const path = require('path');
const qrcode = require('qrcode-terminal');

const authFolder = './baileys_auth_info';

async function startBaileys() {
    // Ensure auth folder exists
    if (!fs.existsSync(authFolder)) {
        fs.mkdirSync(authFolder, { recursive: true });
    }

    // Multi-file auth state
    const { state, saveCreds } = await useMultiFileAuthState(authFolder);

    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: false, // We'll handle QR manually
        logger: {
            level: 'silent' // Reduce logs
        }
    });

    // QR Code handling
    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            console.log('📱 QR Code received, saving...');
            
            // Save QR to file for web interface
            const qrFile = path.join(authFolder, 'qr_code.txt');
            fs.writeFileSync(qrFile, qr);
            
            // Also display in terminal
            qrcode.generate(qr, { small: true });
        }
        
        if (connection === 'close') {
            const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
            console.log('❌ Connection closed due to', lastDisconnect?.error, ', reconnecting:', shouldReconnect);
            
            if (shouldReconnect) {
                setTimeout(startBaileys, 3000);
            }
        } else if (connection === 'open') {
            console.log('✅ WhatsApp connection established!');
            
            // Remove QR file when connected
            const qrFile = path.join(authFolder, 'qr_code.txt');
            if (fs.existsSync(qrFile)) {
                fs.unlinkSync(qrFile);
            }
            
            // Save connection status
            const statusFile = path.join(authFolder, 'status.json');
            fs.writeFileSync(statusFile, JSON.stringify({
                connected: true,
                timestamp: new Date().toISOString()
            }));
        }
    });

    // Save credentials when updated
    sock.ev.on('creds.update', saveCreds);

    // Handle incoming messages
    sock.ev.on('messages.upsert', async (m) => {
        const messages = m.messages;
        
        for (const message of messages) {
            if (!message.key.fromMe && message.message) {
                const from = message.key.remoteJid;
                const messageText = message.message.conversation || 
                                 message.message.extendedTextMessage?.text || 
                                 'Media message';
                
                console.log(`📨 New message from ${from}: ${messageText}`);
                
                // Save to message queue for processing
                const messageData = {
                    from: from,
                    message: messageText,
                    timestamp: new Date().toISOString(),
                    messageId: message.key.id
                };
                
                const queueFile = path.join(authFolder, 'incoming_messages.json');
                let queue = [];
                
                if (fs.existsSync(queueFile)) {
                    const data = fs.readFileSync(queueFile, 'utf8');
                    queue = JSON.parse(data);
                }
                
                queue.push(messageData);
                fs.writeFileSync(queueFile, JSON.stringify(queue, null, 2));
            }
        }
    });

    // Process outgoing message queue
    setInterval(async () => {
        try {
            const queueFile = path.join(authFolder, 'message_queue.json');
            
            if (fs.existsSync(queueFile)) {
                const data = fs.readFileSync(queueFile, 'utf8');
                const queue = JSON.parse(data);
                
                if (queue.length > 0) {
                    for (const msg of queue) {
                        try {
                            await sock.sendMessage(msg.to, { text: msg.message });
                            console.log(`📤 Sent message to ${msg.to}: ${msg.message}`);
                        } catch (error) {
                            console.error(`❌ Failed to send message to ${msg.to}:`, error);
                        }
                    }
                    
                    // Clear queue after processing
                    fs.writeFileSync(queueFile, JSON.stringify([]));
                }
            }
        } catch (error) {
            console.error('❌ Error processing message queue:', error);
        }
    }, 2000); // Check every 2 seconds

    return sock;
}

// Start the service
startBaileys().catch(err => {
    console.error('❌ Failed to start Baileys:', err);
    process.exit(1);
});

// Handle process termination
process.on('SIGINT', () => {
    console.log('👋 Shutting down Baileys service...');
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('👋 Shutting down Baileys service...');
    process.exit(0);
});