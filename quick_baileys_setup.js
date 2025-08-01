#!/usr/bin/env node
/**
 * 🚀 Quick Baileys Setup for WhatsApp Web Integration
 * הגדרת Baileys מהירה לאינטגרציה עם WhatsApp Web
 */

const { createRequire } = require('module');
const fs = require('fs');
const path = require('path');

console.log('🚀 מכין הגדרת Baileys מהירה...');

// Create package.json
const packageJson = {
  "name": "whatsapp-baileys-integration",
  "version": "1.0.0",
  "description": "Baileys WhatsApp Web integration for Hebrew AI Call Center",
  "main": "baileys_client.js",
  "scripts": {
    "start": "node baileys_client.js",
    "setup": "npm install"
  },
  "dependencies": {
    "@whiskeysockets/baileys": "^6.4.0",
    "qrcode-terminal": "^0.12.0",
    "pino": "^8.15.0"
  },
  "author": "Hebrew AI Call Center",
  "license": "MIT"
};

// Create baileys_client.js
const baileysClient = `
const { makeWASocket, DisconnectReason, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const P = require('pino');

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('baileys_auth_info');
    
    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: true,
        logger: P({ level: 'silent' }),
    });

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            console.log('📱 סרוק את ה-QR Code עם WhatsApp:');
            qrcode.generate(qr, { small: true });
        }
        
        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect?.error)?.output?.statusCode !== DisconnectReason.loggedOut;
            console.log('❌ החיבור נסגר:', lastDisconnect?.error, ', מתחבר מחדש:', shouldReconnect);
            if (shouldReconnect) {
                connectToWhatsApp();
            }
        } else if (connection === 'open') {
            console.log('✅ מחובר ל-WhatsApp Web בהצלחה!');
            console.log('🎯 המערכת מוכנה לקבל ולשלוח הודעות');
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('messages.upsert', async (m) => {
        const message = m.messages[0];
        if (!message.key.fromMe && m.type === 'notify') {
            console.log('📥 הודעה חדשה:', message);
            
            // Here we would send to Flask webhook
            // await sendToFlaskWebhook(message);
        }
    });

    return sock;
}

// Run WhatsApp connection
connectToWhatsApp();
`;

try {
    // Write files
    fs.writeFileSync('package.json', JSON.stringify(packageJson, null, 2));
    fs.writeFileSync('baileys_client.js', baileysClient);
    
    console.log('✅ קבצים נוצרו בהצלחה!');
    console.log('');
    console.log('🎯 הוראות המשך:');
    console.log('1. הפעל: npm install');
    console.log('2. הפעל: node baileys_client.js');
    console.log('3. סרוק QR Code בטלפון');
    console.log('4. המערכת תתחבר לWhatsApp Web');
    console.log('');
    console.log('🚀 המערכת מוכנה לשילוב עם הבוט!');
    
} catch (error) {
    console.error('❌ שגיאה:', error.message);
}