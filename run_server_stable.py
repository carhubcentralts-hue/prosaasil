#!/usr/bin/env python3
"""
Stable server runner for Flask/Gunicorn application
"""
import os
import sys
import subprocess
import time

def main():
    # Set environment variables
    os.environ['PORT'] = '5000'
    os.environ['PYTHONPATH'] = '.'
    os.environ['PYTHONUNBUFFERED'] = '1'
    
    print("🚀 Starting Flask/Gunicorn server on port 5000...")
    print("📋 Health endpoint will be: http://127.0.0.1:5000/healthz")
    print("🌐 Main app will be: http://127.0.0.1:5000/")
    
    # Gunicorn command
    cmd = [
        'gunicorn',
        '-k', 'eventlet',
        '-w', '1', 
        'wsgi:app',
        '--bind', '0.0.0.0:5000',
        '--timeout', '120',
        '--preload',
        '--access-logfile', '-',
        '--error-logfile', '-'
    ]
    
    print(f"🔧 Running command: {' '.join(cmd)}")
    
    try:
        # Start the server process
        process = subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()