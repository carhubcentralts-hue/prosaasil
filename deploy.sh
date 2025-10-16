#!/bin/bash
set -e

echo "🚀 Deployment Build - Building Frontend & Backend"
cd /home/runner/workspace

echo "📦 Installing root dependencies..."
npm install

echo "🎨 Building Frontend (Client)..."
cd client
npm install
npm run build
cd ..

echo "✅ Build completed successfully - Frontend ready in client/dist/"