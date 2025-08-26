"""
Start WebSocket server נפרד לתמלול לייב
"""
import asyncio
import os
import sys

# Add server to path
sys.path.append('server')

from server.websocket_server import start_websocket_server

async def main():
    """Start the WebSocket server"""
    print("🚀 Starting Native WebSocket Server for Hebrew Live Transcription")
    
    # Start WebSocket server on port 8765
    server = await start_websocket_server("0.0.0.0", 8765)
    
    print("✅ WebSocket Server started on 0.0.0.0:8765")
    print("🔍 Waiting for Twilio connections...")
    
    # Keep server running
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())