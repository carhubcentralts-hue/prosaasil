#!/usr/bin/env bash
set -euo pipefail

echo "🏗️ PRODUCTION BUILD - Phase 1: Python dependencies"
pip install .

echo "🏗️ PRODUCTION BUILD - Phase 2: Frontend"
cd client
echo "📦 Installing frontend dependencies..."
npm install --prefer-offline --no-audit --no-fund --legacy-peer-deps
echo "🔨 Building frontend with Vite..."
npm run build
cd ..

echo "✅ PRODUCTION BUILD COMPLETE"
echo "📦 Python packages installed"
echo "📦 Frontend built at client/dist/"
