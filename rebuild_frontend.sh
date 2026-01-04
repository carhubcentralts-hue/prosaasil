#!/bin/bash
# 🎨 Rebuild Frontend - בנייה מחדש של הפרונט

set -e

echo "🎨 Starting frontend rebuild..."
echo ""

cd client

echo "📦 Installing dependencies..."
npm install

echo "🔨 Building frontend..."
npm run build

echo ""
echo "✅ Frontend rebuilt successfully!"
echo "📁 Build output: client/dist/"
echo ""
echo "⚠️  Next steps:"
echo "   1. Restart: ./start_production.sh"
echo "   2. Clear browser cache: Ctrl + Shift + Delete"
echo "   3. Hard refresh: Ctrl + F5"
echo ""
