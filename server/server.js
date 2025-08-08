const express = require('express');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../dist')));

// API routes
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', message: 'Hebrew AI Call Center CRM is running' });
});

app.get('/api/dashboard', (req, res) => {
  res.json({ 
    message: 'Dashboard data',
    stats: {
      totalCalls: 127,
      activeBusiness: 'שי דירות ומשרדים בע״מ',
      status: 'operational'
    }
  });
});

// Serve React app for all other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../dist/index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Hebrew AI Call Center CRM server running on port ${PORT}`);
  console.log(`📍 Accessible at: http://0.0.0.0:${PORT}`);
});