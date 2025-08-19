#!/usr/bin/env python3
"""
Super Stable Server Launcher for Hebrew AI Call Center
Auto-restart on crash with comprehensive error handling
"""
import subprocess
import time
import signal
import sys
import os
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/supervisor.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

class ServerSupervisor:
    def __init__(self):
        self.process = None
        self.restart_count = 0
        self.max_restarts = 50
        self.running = True
        
    def signal_handler(self, signum, frame):
        log.info("🛑 Shutdown signal received")
        self.running = False
        if self.process:
            self.process.terminate()
        sys.exit(0)
        
    def start_server(self):
        """Start the Gunicorn server with error recovery"""
        cmd = [
            sys.executable, "-m", "gunicorn",
            "-k", "eventlet",
            "-w", "1", 
            "-b", "0.0.0.0:5000",
            "--timeout", "120",
            "--keep-alive", "2",
            "--max-requests", "1000",
            "--max-requests-jitter", "100",
            "--preload",
            "main:app"
        ]
        
        log.info(f"🚀 Starting server (attempt {self.restart_count + 1})")
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            cwd=os.getcwd()
        )
    
    def monitor_server(self):
        """Monitor server and restart on failure"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        while self.running and self.restart_count < self.max_restarts:
            try:
                self.process = self.start_server()
                log.info(f"✅ Server started with PID {self.process.pid}")
                
                # Monitor the process
                while self.process.poll() is None and self.running:
                    time.sleep(5)
                    
                if not self.running:
                    break
                    
                # Process died
                exit_code = self.process.poll()
                log.error(f"❌ Server died with exit code {exit_code}")
                
                self.restart_count += 1
                if self.restart_count < self.max_restarts:
                    wait_time = min(10 * self.restart_count, 60)  # Exponential backoff
                    log.info(f"⏰ Waiting {wait_time}s before restart...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                log.error(f"❌ Supervisor error: {e}")
                self.restart_count += 1
                time.sleep(10)
                
        log.info("🛑 Supervisor shutting down")

if __name__ == "__main__":
    print("🚀 Starting Hebrew AI Call Center Super Stable Server")
    supervisor = ServerSupervisor()
    supervisor.monitor_server()