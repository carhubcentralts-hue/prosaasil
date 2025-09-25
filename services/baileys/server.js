// Single entrypoint that boots the real service.
// Do NOT add any other express() or app.listen() here.
const baileys = require('../whatsapp/baileys_service');

// ✅ CRITICAL FIX: Actually start the service!
console.log('🚀 Starting Baileys service...');
baileys.start();