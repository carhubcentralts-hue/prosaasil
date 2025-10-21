#!/usr/bin/env bash
set -euo pipefail

echo "🔨 Building Frontend for Production..."
cd client

echo "📦 Installing Node dependencies..."
npm install

echo "🏗️ Building React app with Vite..."
npm run build

echo "✅ Frontend build complete!"
ls -lah dist/

cd ..
echo "✅ All builds complete - ready for deployment!"
