#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hebrew AI Call Center CRM - Main Entry Point
Wrapper script to start the Flask server from the correct directory
"""

import os
import sys
import subprocess
import signal
import time

def main():
    """Main entry point for the Hebrew AI Call Center CRM"""
    print("🚀 Starting Hebrew AI Call Center CRM...")
    
    # Change to server directory
    server_dir = os.path.join(os.path.dirname(__file__), 'server')
    
    if not os.path.exists(server_dir):
        print("❌ Error: server directory not found!")
        sys.exit(1)
    
    server_main = os.path.join(server_dir, 'main.py')
    if not os.path.exists(server_main):
        print("❌ Error: server/main.py not found!")
        sys.exit(1)
    
    # Change to server directory and run main.py
    original_cwd = os.getcwd()
    
    try:
        os.chdir(server_dir)
        print(f"📁 Changed to directory: {server_dir}")
        print("🌟 Starting Flask server...")
        
        # Execute the server main.py
        subprocess.run([sys.executable, 'main.py'], check=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down gracefully...")
    except subprocess.CalledProcessError as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
    finally:
        os.chdir(original_cwd)

if __name__ == "__main__":
    main()