const express = require('express')
const pino = require('pino')()
const qrcode = require('qrcode-terminal')
const {
  makeWASocket,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  DisconnectReason
} = require('@whiskeysockets/baileys')

const app = express()
app.use(express.json())

let sock = null
let lastQR = null
let ready = false

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState('./auth')
  const { version } = await fetchLatestBaileysVersion()
  sock = makeWASocket({
    version,
    printQRInTerminal: false,
    auth: state,
    browser: ['Shai CRM','Chrome','120']
  })

  sock.ev.on('creds.update', saveCreds)
  sock.ev.on('connection.update', (u) => {
    const { connection, qr, lastDisconnect } = u
    if (qr) {
      lastQR = qr
      qrcode.generate(qr, { small: true })
      pino.info('QR updated')
    }
    if (connection === 'open') {
      ready = true
      lastQR = null
      pino.info('Baileys connected ✅')
    }
    if (connection === 'close') {
      ready = false
      const code = lastDisconnect?.error?.output?.statusCode
      if (code !== DisconnectReason.loggedOut) {
        pino.warn({ code }, 'reconnecting…')
        start().catch(err => pino.error(err))
      } else {
        pino.error('logged out – delete ./auth to relogin')
      }
    }
  })

  // Listen for incoming messages and forward to Flask backend for AI processing
  sock.ev.on('messages.upsert', async (m) => {
    const messages = m.messages || [];
    for (const message of messages) {
      // Skip if message is from us (fromMe = true)
      if (message.key && message.key.fromMe) {
        continue;
      }
      
      // Extract message data
      const from = message.key.remoteJid;
      const messageText = message.message?.conversation || 
                        message.message?.extendedTextMessage?.text || 
                        "[Media/Non-text message]";
      
      pino.info(`📨 Inbound WhatsApp from ${from}: ${messageText}`);
      
      try {
        // Forward to Flask backend for AI processing
        const axios = require('axios');
        const response = await axios.post('http://127.0.0.1:5000/api/whatsapp/baileys/inbound', {
          from: from,
          text: messageText,
          messageId: message.key.id,
          timestamp: Date.now(),
          rawMessage: message
        }, {
          headers: {
            'Content-Type': 'application/json',
            'User-Agent': 'Baileys-Internal/1.0'
          },
          timeout: 10000
        });
        
        pino.info(`✅ Message forwarded to Flask: ${response.status}`);
      } catch (error) {
        pino.error(`❌ Failed to forward message to Flask: ${error.message}`);
      }
    }
  })
}

app.get('/health', (req, res) => {
  res.json({ ok: true, ready })
})

app.get('/qr', (req, res) => {
  if (lastQR) return res.json({ qr: lastQR })
  res.json({ qr: null, ready })
})

app.post('/send', async (req, res) => {
  try {
    if (!ready) return res.status(503).json({ error: 'not_ready' })
    const { to, text } = req.body
    if (!to || !text) return res.status(400).json({ error: 'missing_params' })
    const jid = to.endsWith('@s.whatsapp.net') ? to : to.replace(/[^\d]/g,'') + '@s.whatsapp.net'
    await sock.sendMessage(jid, { text })
    res.json({ ok: true })
  } catch (e) {
    pino.error(e)
    res.status(500).json({ error: 'send_failed' })
  }
})

const PORT = Number(process.env.BAILEYS_PORT || process.env.PORT || 3300)
app.listen(PORT, '127.0.0.1', () => pino.info(`Baileys HTTP on :${PORT}`))

// Add uncaught exception handlers
process.on('uncaughtException', (err) => {
  pino.error({ err }, 'Uncaught exception - continuing')
})

process.on('unhandledRejection', (reason, promise) => {
  pino.error({ reason, promise }, 'Unhandled rejection - continuing')
})

start().catch(err => {
  pino.error(err)
  // Don't exit - try to reconnect
  setTimeout(() => start().catch(() => {}), 5000)
})