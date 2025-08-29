#!/usr/bin/env python3
"""
Ultra-simple React server
"""
import http.server
import socketserver
import os

class ReactHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="client/dist", **kwargs)

PORT = 5000

if __name__ == "__main__":
    print(f"🚀 Starting React server on port {PORT}")
    print("🎯 Serving from client/dist/")
    
    with socketserver.TCPServer(("0.0.0.0", PORT), ReactHandler) as httpd:
        print(f"✅ Server ready at http://0.0.0.0:{PORT}")
        httpd.serve_forever()