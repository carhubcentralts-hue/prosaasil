// Single entrypoint that boots the real service.
// Do NOT add any other express() or app.listen() here.
require('../whatsapp/baileys_service').start();