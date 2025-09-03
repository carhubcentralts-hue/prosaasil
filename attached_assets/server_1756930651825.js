#!/usr/bin/env node

const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5000;

// Serve static files from React build
app.use(express.static(path.join(__dirname, 'client/dist')));

// Handle React Router (send all requests to index.html)
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'client/dist/index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 React Server running on port ${PORT}`);
  console.log(`📱 App available at http://0.0.0.0:${PORT}`);
});