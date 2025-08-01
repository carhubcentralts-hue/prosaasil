#!/bin/bash

# Find Node.js path
NODE_PATH=$(find /nix/store -name "nodejs-20*" -type d | head -1)/bin

if [ -z "$NODE_PATH" ]; then
    echo "❌ Node.js לא נמצא"
    exit 1
fi

# Export PATH
export PATH="$NODE_PATH:$PATH"

cd /home/runner/workspace

echo "🧹 מנקה חיבור ישן..."
rm -rf baileys_auth_info

echo "📱 מפעיל Baileys..."
echo "🎯 QR Code יופיע - סרוק אותו עם WhatsApp"
echo ""

# Run Baileys
node baileys_client.js