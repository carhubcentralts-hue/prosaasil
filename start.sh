#!/bin/bash
# Production start script for Hebrew AI Call Center CRM
# סקריפט הפעלה לייצור עבור מערכת CRM מוקד שיחות AI בעברית

echo "🚀 Starting Hebrew AI Call Center CRM - Production Mode"
echo "======================================================="

# Set production environment
export FLASK_ENV=production
export FLASK_DEBUG=false
export PYTHONPATH="."

# Set default port if not provided
export PORT=${PORT:-5000}
export HOST=${HOST:-0.0.0.0}

echo "📍 Starting on $HOST:$PORT"
echo "🕐 $(date)"

# Start the main Python application
exec python main.py