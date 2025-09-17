// Test minimal Baileys server
const express = require('express');
const app = express();

const PORT = process.env.BAILEYS_PORT || 3300;
const INTERNAL_SECRET = process.env.INTERNAL_SECRET;

console.log('🔧 Starting minimal test server...');
console.log('PORT:', PORT);
console.log('INTERNAL_SECRET:', INTERNAL_SECRET ? 'SET' : 'MISSING');

if (!INTERNAL_SECRET) {
  console.error('❌ INTERNAL_SECRET missing');
  process.exit(1);
}

// Basic healthz endpoint
app.get('/healthz', (req, res) => {
  console.log('📍 healthz called');
  res.status(200).send('ok');
});

// Test endpoint
app.get('/test', (req, res) => {
  console.log('📍 test called');
  res.json({ message: 'minimal server works!' });
});

// Error handlers
process.on('unhandledRejection', err => console.error('[UNHANDLED]', err));
process.on('uncaughtException', err => console.error('[UNCAUGHT]', err));

app.listen(PORT, '127.0.0.1', () => {
  console.log(`✅ Minimal server listening on ${PORT}`);
});

// Keep alive
setInterval(() => console.log('💓 server alive'), 10000);