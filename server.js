#!/usr/bin/env node
/**
 * DEVELOPMENT-ONLY React Server
 * ⚠️ DO NOT RUN IN PRODUCTION - SPA is served by Flask
 * Use this only for frontend development when working separately from Flask
 */

const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;  // Changed to avoid conflict with Flask

console.log("⚠️ DEVELOPMENT SERVER - Frontend only!");
console.log("⚠️ In production, React SPA is served by Flask on port 5000");

// Serve static files from React build
app.use(express.static(path.join(__dirname, 'client/dist')));

// Handle React Router (send all requests to index.html)
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'client/dist/index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 DEV-ONLY React Server running on port ${PORT}`);
  console.log(`📱 Dev app available at http://0.0.0.0:${PORT}`);
  console.log(`⚠️ Use Flask on port 5000 for production!`);
});