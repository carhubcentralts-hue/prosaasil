#!/bin/bash
# Replit Production Deployment Script
# סקריפט פריסה לייצור עבור Replit

echo "🚀 Hebrew AI Call Center - Production Deployment"
echo "=================================================="

# Check if running on Replit
if [ -z "$REPL_ID" ]; then
    echo "⚠️ Warning: Not running on Replit environment"
fi

# Set production environment
export FLASK_ENV=production
export FLASK_DEBUG=false

echo "📋 Pre-deployment checks..."

# Check Python version
python_version=$(python --version 2>&1)
echo "✅ Python version: $python_version"

# Check required environment variables
required_vars=("SESSION_SECRET" "OPENAI_API_KEY" "TWILIO_ACCOUNT_SID" "TWILIO_AUTH_TOKEN" "DATABASE_URL")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Missing environment variables: ${missing_vars[*]}"
    echo "Please set these in Replit Secrets:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

echo "✅ All environment variables present"

# Check database connection
echo "🗄️ Testing database connection..."
python -c "
from app import app, db
with app.app_context():
    try:
        db.session.execute('SELECT 1').scalar()
        print('✅ Database connection successful')
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        exit(1)
"

# Install/update dependencies if needed
echo "📦 Checking dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
    echo "✅ Dependencies checked"
fi

# Create necessary directories
mkdir -p static/voice_responses
mkdir -p logs
mkdir -p docs/backups

echo "📁 Directories created"

# Database migrations (if needed)
echo "🗄️ Running database setup..."
python -c "
from app import app, db
import models
import crm_models

with app.app_context():
    db.create_all()
    print('✅ Database tables ensured')
"

# Start background services
echo "🧹 Starting background services..."
python -c "
from auto_cleanup_background import background_cleanup
background_cleanup.start_scheduler()
print('✅ Background cleanup scheduler started')
" &

# Performance optimizations for Replit
echo "⚡ Applying Replit optimizations..."

# Set worker count based on available resources
if [ "$REPL_OWNER" ]; then
    # Replit Core/Pro settings
    export GUNICORN_WORKERS=2
    export GUNICORN_TIMEOUT=30
    export GUNICORN_MAX_REQUESTS=1000
else
    # Standard Replit settings
    export GUNICORN_WORKERS=1
    export GUNICORN_TIMEOUT=60
    export GUNICORN_MAX_REQUESTS=500
fi

echo "✅ Optimizations applied"

# Health check function
health_check() {
    local max_attempts=30
    local attempt=1
    
    echo "🏥 Performing health check..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s http://localhost:5000/ > /dev/null 2>&1; then
            echo "✅ Application is healthy"
            return 0
        fi
        
        echo "⏳ Attempt $attempt/$max_attempts - waiting for application..."
        sleep 2
        ((attempt++))
    done
    
    echo "❌ Health check failed after $max_attempts attempts"
    return 1
}

# Start the main application
echo "🚀 Starting main application..."

if [ "$1" = "dev" ]; then
    # Development mode
    echo "🔧 Running in development mode"
    python main.py
else
    # Production mode
    echo "🏭 Running in production mode"
    
    # Start Gunicorn in background
    gunicorn \
        --bind 0.0.0.0:5000 \
        --workers $GUNICORN_WORKERS \
        --timeout $GUNICORN_TIMEOUT \
        --max-requests $GUNICORN_MAX_REQUESTS \
        --preload \
        --access-logfile logs/access.log \
        --error-logfile logs/error.log \
        --log-level info \
        main:app &
    
    # Store PID for cleanup
    GUNICORN_PID=$!
    echo $GUNICORN_PID > gunicorn.pid
    
    # Wait for application to start
    sleep 5
    
    # Perform health check
    if health_check; then
        echo "🎉 Deployment successful!"
        echo "🌐 Application is running on http://localhost:5000"
        echo "📊 Admin Dashboard: http://localhost:5000/admin-dashboard"
        echo "📱 WhatsApp Dashboard: http://localhost:5000/whatsapp/conversations"
        echo "💼 CRM System: http://localhost:5000/crm"
        echo ""
        echo "🔑 Default admin login: שי / admin123"
        echo ""
        echo "📋 To monitor logs:"
        echo "  tail -f logs/access.log"
        echo "  tail -f logs/error.log"
        echo ""
        echo "🛑 To stop: kill $GUNICORN_PID"
        
        # Keep script running to monitor
        wait $GUNICORN_PID
    else
        echo "❌ Deployment failed - application not responding"
        kill $GUNICORN_PID 2>/dev/null
        exit 1
    fi
fi