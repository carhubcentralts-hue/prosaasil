import makeWASocket, { useSingleFileAuthState, DisconnectReason } from "@adiwajshing/baileys";
import express from "express";
import QRCode from "qrcode";
import pino from "pino";

const PORT = process.env.PORT || 3001;
const { state, saveState } = useSingleFileAuthState("./auth.baileys.json"); // נשמר בדיסק (רסטארט שורד)
const log = pino({ level: "info" });

let sock;
let lastQR = null;
let connectionState = "starting";
let meJid = null;

async function start() {
  sock = makeWASocket({
    printQRInTerminal: false,
    auth: state,
    logger: log
  });

  sock.ev.on("creds.update", saveState);

  sock.ev.on("connection.update", async (u) => {
    const { qr, connection, lastDisconnect } = u;
    if (qr) {
      lastQR = await QRCode.toDataURL(qr);
    }
    if (connection) connectionState = connection;
    if (connection === "close") {
      const code = lastDisconnect?.error?.output?.statusCode;
      if (code !== DisconnectReason.loggedOut) {
        log.warn({ code }, "conn closed – reconnecting");
        setTimeout(start, 1500);
      } else {
        log.error("logged out – delete auth.baileys.json to relogin");
      }
    }
  });

  sock.ev.on("contacts.upsert", (c) => (meJid = sock.user?.id || meJid));
}
await start();

const app = express();
app.use(express.json());

// בריאות
app.get("/health", (_, res) => {
  res.json({ ok: true, state: connectionState, me: meJid || null, hasQR: !!lastQR });
});

// QR (מחזיר dataURL)
app.get("/qr", (_, res) => {
  if (!lastQR) return res.status(404).json({ ok: false, message: "no qr yet" });
  res.json({ ok: true, qr: lastQR });
});

// שליחת הודעה (טקסט)
app.post("/send", async (req, res) => {
  try {
    const { to_e164, text } = req.body || {};
    if (!to_e164 || !text) return res.status(400).json({ ok: false, message: "to_e164 & text required" });
    const jid = to_e164.replace(/\D/g, "") + "@s.whatsapp.net";
    await sock.sendMessage(jid, { text });
    res.json({ ok: true });
  } catch (e) {
    log.error(e);
    res.status(500).json({ ok: false, message: "send failed" });
  }
});

app.listen(PORT, "0.0.0.0", () => log.info({ PORT }, "Baileys HTTP up"));