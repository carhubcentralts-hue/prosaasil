#!/usr/bin/env python3
"""
Production startup script with WebSocket support
Run this instead of npm run dev for WebSocket Media Streams
"""
import subprocess
import sys
import os

def main():
    print("🚀 Starting Hebrew AI Call Center with WebSocket support...")
    
    # Install dependencies if needed
    try:
        import flask_sock
        import eventlet
        print("✅ WebSocket dependencies available")
    except ImportError:
        print("📦 Installing WebSocket dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", 
                             "flask-sock==0.6.0", "simple-websocket==1.0.0", "eventlet==0.36.1"])
    
    # Set environment for production
    os.environ.setdefault('FLASK_ENV', 'production')
    
    # Start gunicorn with eventlet worker for WebSocket support
    cmd = [
        sys.executable, "-m", "gunicorn",
        "-k", "eventlet",
        "-w", "1", 
        "-b", "0.0.0.0:5000",
        "--timeout", "120",
        "--keep-alive", "2",
        "main:app"
    ]
    
    print(f"🚀 Running: {' '.join(cmd)}")
    subprocess.run(cmd)

if __name__ == "__main__":
    main()