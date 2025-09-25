#!/bin/bash
set -e

echo "🚀 Deployment Build - Installing only Node.js packages"
cd /home/runner/workspace
npm install

echo "✅ Build completed successfully"