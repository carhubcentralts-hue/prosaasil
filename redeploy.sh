#!/bin/bash
# 🚀 Full Redeploy Script - פריסה מלאה עם ניקוי cache

set -e  # Exit on error

echo "========================================"
echo "🚀 ProSaaS - Full Redeploy"
echo "========================================"
echo ""

# Step 1: Stop containers
echo "⏹️  [1/5] Stopping all containers..."
docker compose down
echo "✅ Containers stopped"
echo ""

# Step 2: Clean Docker cache
echo "🧹 [2/5] Cleaning Docker cache..."
echo "⚠️  This will remove ALL unused Docker data!"
read -p "Continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled"
    exit 1
fi
docker system prune -af --volumes
echo "✅ Cache cleaned"
echo ""

# Step 3: Build without cache
echo "🔨 [3/5] Building all containers (no cache)..."
docker compose build --no-cache
echo "✅ Build completed"
echo ""

# Step 4: Start services
echo "🚀 [4/5] Starting all services..."
docker compose up -d
echo "✅ Services started"
echo ""

# Step 5: Wait and show status
echo "⏳ [5/5] Waiting for services to be ready..."
sleep 5
docker compose ps
echo ""

# Show logs
echo "📋 Recent logs from all services:"
docker compose logs --tail=20
echo ""

echo "========================================"
echo "✅ Deployment Complete!"
echo "========================================"
echo ""
echo "⚠️  IMPORTANT: Clear browser cache to see frontend changes!"
echo ""
echo "🔧 Quick commands:"
echo "   View logs:    docker compose logs -f"
echo "   View status:  docker compose ps"
echo "   Restart:      docker compose restart"
echo "   Stop all:     docker compose down"
echo ""
echo "🧪 Test the fixes:"
echo "   1. Email: Send test email to verify business.name works"
echo "   2. TTS: Test voice preview in AI settings"
echo "   3. UI: Check Emails page has footer edit field"
echo ""
