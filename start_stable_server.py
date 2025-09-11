#!/usr/bin/env python3
"""
Stable server startup for AgentLocator CRM system
Uses Eventlet WSGI server for persistent operation
"""

import os
import eventlet
eventlet.monkey_patch()  # Must be first for proper WebSocket support

from eventlet import wsgi
import wsgi as wsgi_module

def main():
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 Starting AgentLocator stable server on 0.0.0.0:{port}")
    
    # Create Eventlet listener
    listener = eventlet.listen(("0.0.0.0", port))
    
    # Start WSGI server with logging
    wsgi.server(listener, wsgi_module.app, log_output=True)

if __name__ == "__main__":
    main()
