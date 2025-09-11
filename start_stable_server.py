#!/usr/bin/env python3
"""
Stable server starter for Replit environment
Handles common stability issues with eventlet and gunicorn
"""
import os
import sys
import signal
import time
import subprocess
from pathlib import Path

# Set optimal environment variables for stability
os.environ.update({
    'PYTHONUNBUFFERED': '1',
    'PYTHONPATH': '.',
    'EVENTLET_NO_GREENDNS': '1',
    'EVENTLET_HUB': 'poll',
    'GUNICORN_CMD_ARGS': '--worker-tmp-dir /dev/shm --worker-connections 1000 --max-requests 1000 --max-requests-jitter 100'
})

def start_server():
    """Start server with proper error handling and restart logic"""
    port = int(os.getenv("PORT", "5000"))
    
    # Optimized gunicorn command for Replit stability
    cmd = [
        'python', '-m', 'gunicorn', 
        'wsgi:app',
        '-k', 'eventlet',
        '-w', '1',
        '-b', f'0.0.0.0:{port}',
        '--timeout', '120',
        '--keep-alive', '2',
        '--max-requests', '1000',
        '--max-requests-jitter', '100',
        '--worker-connections', '1000',
        '--log-level', 'info',
        '--access-logfile', '-',
        '--error-logfile', '-',
        '--preload',
        '--worker-tmp-dir', '/dev/shm'
    ]
    
    print(f"🚀 Starting stable server on port {port}")
    print(f"📝 Command: {' '.join(cmd)}")
    
    process = None  # Initialize process variable
    try:
        # Start the server
        process = subprocess.Popen(cmd, 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.STDOUT,
                                 universal_newlines=True,
                                 bufsize=1)
        
        # Stream output in real-time
        if process.stdout:  # Check stdout is not None
            for line in process.stdout:
                print(line.rstrip())
                sys.stdout.flush()
            
    except KeyboardInterrupt:
        print("\n🛑 Server shutdown requested")
        if process:
            process.terminate()
            process.wait()
    except Exception as e:
        print(f"❌ Server error: {e}")
        if process:
            process.terminate()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(start_server())