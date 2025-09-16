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

const PORT = Number(process.env.PORT || 3001)
app.listen(PORT, '0.0.0.0', () => pino.info(`Baileys HTTP on :${PORT}`))

start().catch(err => {
  pino.error(err)
  process.exit(1)
})