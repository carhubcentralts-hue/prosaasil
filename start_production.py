#!/usr/bin/env python3
"""
🎯 PRODUCTION STARTUP - WebSocket Ready!
Required for Twilio Media Streams support
"""
import os
import sys
import subprocess

def main():
    """Start with gunicorn + eventlet for full WebSocket support"""
    print("🚀 Hebrew AI Call Center - Production WebSocket Mode")
    print("=" * 60)
    
    # Set production environment
    os.environ['FLASK_ENV'] = 'production'
    os.environ['PYTHONPATH'] = '.'
    
    # Get port from environment
    port = os.environ.get('PORT', '5000')
    
    # Production gunicorn command with eventlet for WebSocket
    cmd = [
        sys.executable, '-m', 'gunicorn',
        '--worker-class', 'eventlet',
        '--workers', '1',
        '--bind', f'0.0.0.0:{port}',
        '--timeout', '300',
        '--keepalive', '2',
        '--access-logfile', '-',
        '--error-logfile', '-',
        '--log-level', 'info',
        'main:app'
    ]
    
    print(f"📡 Production Server: 0.0.0.0:{port}")
    print(f"🔗 WebSocket Endpoint: /ws/twilio-media") 
    print(f"📞 Webhook Ready: /webhook/incoming_call")
    print(f"✅ OpenAI Dynamic Greetings: ON")
    print("=" * 60)
    
    # Start the production server
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 Production server stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Gunicorn failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Startup error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()