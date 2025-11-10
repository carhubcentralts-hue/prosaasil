#!/usr/bin/env bash
set -euo pipefail

echo "🏗️ PRODUCTION BUILD START - $(date)"
echo "⏱️  Estimated time: 3-5 minutes"
echo ""

# Phase 1: Python dependencies (SLOWEST - numpy, scipy, reportlab)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏗️ Phase 1/3: Python dependencies (2-3 min)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Installing heavy packages (numpy, scipy, reportlab)..."
pip install --no-cache-dir --quiet . || {
    echo "❌ Python install failed! Retrying with verbose output..."
    pip install .
}
echo "✅ Python packages installed - $(date)"
echo ""

# Phase 2: Frontend (FAST with cache)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏗️ Phase 2/3: Frontend build (30-60 sec)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd client
echo "📦 Installing frontend dependencies..."
npm install --prefer-offline --no-audit --no-fund --legacy-peer-deps --loglevel error
echo "🔨 Building frontend with Vite..."
npm run build
cd ..
echo "✅ Frontend built - $(date)"
echo ""

# Phase 3: Baileys (FAST)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏗️ Phase 3/3: Baileys WhatsApp (30 sec)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd services/whatsapp
echo "📦 Installing Baileys dependencies..."
npm install --prefer-offline --no-audit --no-fund --legacy-peer-deps --loglevel error
cd ../..
echo "✅ Baileys ready - $(date)"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ PRODUCTION BUILD COMPLETE - $(date)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📦 Python packages: ✅ Installed"
echo "📦 Frontend build:  ✅ client/dist/"
echo "📦 Baileys service: ✅ services/whatsapp/node_modules/"
echo ""
echo "🚀 Ready for deployment!"
