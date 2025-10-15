// Single entrypoint that boots the real service.
// Do NOT add any other express() or app.listen() here.
const baileys = require('../whatsapp/baileys_service');

// ✅ CRITICAL FIX: Actually start the service!
console.log('🚀 Starting Baileys service...');
const server = baileys.start();

// Keep process alive - prevent exit after start()
if (server) {
  console.log('✅ Baileys server started and running');
  // Handle graceful shutdown
  process.on('SIGTERM', () => {
    console.log('🛑 SIGTERM received, shutting down...');
    server.close(() => process.exit(0));
  });
  process.on('SIGINT', () => {
    console.log('🛑 SIGINT received, shutting down...');
    server.close(() => process.exit(0));
  });
} else {
  console.error('❌ Failed to start Baileys server');
  process.exit(1);
}