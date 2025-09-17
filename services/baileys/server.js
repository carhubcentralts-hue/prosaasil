// Direct require for better stability in background mode
try {
  require('../whatsapp/baileys_service.js');
  console.log('✅ Baileys service module loaded directly');
} catch (e) {
  console.error('❌ Failed to load baileys service:', e);
  process.exit(1);
}