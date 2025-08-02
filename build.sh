#!/bin/bash
# Build script for Hebrew AI Call Center CRM deployment
# סקריפט בניה לפריסת מערכת CRM מוקד שיחות AI בעברית

echo "🚀 Building Hebrew AI Call Center CRM..."
echo "=================================================="

# Set environment variables
export FLASK_ENV=production
export FLASK_DEBUG=false

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p static/voice_responses
mkdir -p logs
mkdir -p docs/backups
mkdir -p baileys_auth_info

# Check Python version
python_version=$(python --version 2>&1)
echo "✅ Python version: $python_version"

# Install/upgrade Python dependencies from pyproject.toml
echo "📦 Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install .

# Setup database
echo "🗄️ Setting up database..."
python -c "
from app import app, db
import models
import crm_models

with app.app_context():
    try:
        db.create_all()
        print('✅ Database tables created successfully')
    except Exception as e:
        print(f'⚠️ Database setup warning: {e}')
"

# Install Node.js dependencies for Baileys WhatsApp service
echo "📱 Installing WhatsApp service dependencies..."
if [ -f "package.json" ]; then
    npm install --production
    echo "✅ Node.js dependencies installed"
fi

echo "✅ Build completed successfully!"
echo "🚀 Ready for deployment with 'python main.py'"