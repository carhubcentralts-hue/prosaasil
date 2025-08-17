#!/usr/bin/env python3
"""
Production startup script with gunicorn + eventlet
Required for WebSocket support in Twilio Media Streams
"""
import os
import sys
import subprocess

def main():
    """Start the application with gunicorn + eventlet for WebSocket support"""
    print("🚀 Starting Hebrew AI Call Center with WebSocket support...")
    
    # Set environment variables
    os.environ['FLASK_ENV'] = 'production'
    
    # Get port from environment
    port = os.environ.get('PORT', '5000')
    
    # Gunicorn command with eventlet worker for WebSocket support
    cmd = [
        sys.executable, '-m', 'gunicorn',
        '--worker-class', 'eventlet',
        '--workers', '1',
        '--bind', f'0.0.0.0:{port}',
        '--timeout', '120',
        '--access-logfile', '-',
        '--error-logfile', '-',
        'main:app'
    ]
    
    print(f"🔗 Command: {' '.join(cmd)}")
    print(f"🌐 Server will start on port {port}")
    print("✅ WebSocket /ws/twilio-media will be available for Twilio Media Streams")
    
    # Start the server
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()