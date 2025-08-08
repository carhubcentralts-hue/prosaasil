#!/usr/bin/env bash
set -e

echo "🚀 Starting Hebrew AI Call Center CRM - SAFE MODE"

# Python env
echo "📦 Setting up Python virtual environment..."
python3 -m venv .venv || true
source .venv/bin/activate
python -m pip install -U pip wheel

echo "📥 Installing Python dependencies..."
pip install -r server/requirements.txt

echo "🔥 Starting Flask backend on port 5000..."
cd server
python main.py &
FLASK_PID=$!
cd ..

# Wait for port 5000 so Preview doesn't get stuck
echo "⏳ Waiting for Flask to start on port 5000..."
python - <<'PY'
import socket,time,sys
for _ in range(120):
    try:
        s=socket.socket(); s.settimeout(1)
        s.connect(("127.0.0.1",5000)); s.close()
        print("✅ Flask backend ready on port 5000")
        sys.exit(0)
    except Exception: time.sleep(1)
print("❌ Flask failed to start on port 5000")
sys.exit(1)
PY

echo "🎯 Hebrew AI Call Center CRM is running!"
echo "📱 Flask Backend: http://localhost:5000"
echo "💻 Frontend (manual): cd client && npm run dev"

# Keep the script running
wait $FLASK_PID