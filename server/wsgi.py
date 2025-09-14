#!/usr/bin/env python3
"""
WSGI Entry Point for Hebrew AI Call Center CRM
TEMPORARY FIX: Export plain Flask app without WebSocket composite
"""

import os
from server.app_factory import create_app

# Create plain Flask app without WebSocket wrapper
app = create_app()

if __name__ == "__main__":
    # For development
    app.run(host="0.0.0.0", port=5000, debug=True)