"""
Media Gateway Service - Main entry point
Bridges Asterisk RTP audio with OpenAI Realtime API WebSocket
"""
import os
import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MediaGatewayService:
    """
    Media Gateway: Asterisk RTP ↔ OpenAI Realtime WebSocket
    
    Responsibilities:
    - Receive RTP (g711 ulaw) from Asterisk ExternalMedia
    - Convert to PCM16 for OpenAI Realtime API
    - Send audio to OpenAI via WebSocket
    - Receive AI audio from OpenAI
    - Convert back to g711 ulaw
    - Send RTP back to Asterisk
    
    Key Features:
    - 20ms frame buffering
    - Jitter buffer for RTP
    - Reconnect guards for WS
    - Audio quality metrics
    - Debug audio dump (optional)
    """
    
    def __init__(
        self,
        rtp_host: str = "0.0.0.0",
        rtp_port_range: tuple = (10000, 20000),
        openai_api_key: Optional[str] = None,
        dump_audio: bool = False
    ):
        """
        Initialize Media Gateway.
        
        Args:
            rtp_host: Host to bind RTP server
            rtp_port_range: RTP port range (start, end)
            openai_api_key: OpenAI API key (default from env)
            dump_audio: Enable audio dump for debugging
        """
        self.rtp_host = rtp_host
        self.rtp_port_start, self.rtp_port_end = rtp_port_range
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.dump_audio = dump_audio
        
        # Active call sessions: {call_id: session}
        self.active_sessions: Dict[str, Any] = {}
        
        # RTP server
        self.rtp_server = None
        
        logger.info(f"[MEDIA_GATEWAY] Initialized: rtp={rtp_host}:{rtp_port_start}-{rtp_port_end}")
    
    async def start(self):
        """Start Media Gateway service."""
        logger.info("[MEDIA_GATEWAY] Starting service...")
        
        # Start RTP server
        from server.services.media_gateway.rtp_server import RTPServer
        
        self.rtp_server = RTPServer(
            host=self.rtp_host,
            port_start=self.rtp_port_start,
            port_end=self.rtp_port_end,
            on_packet=self._handle_rtp_packet
        )
        
        await self.rtp_server.start()
        
        logger.info("[MEDIA_GATEWAY] ✅ Service started")
    
    async def stop(self):
        """Stop Media Gateway service."""
        logger.info("[MEDIA_GATEWAY] Stopping service...")
        
        # Close all active sessions
        for call_id in list(self.active_sessions.keys()):
            await self.end_call_session(call_id)
        
        # Stop RTP server
        if self.rtp_server:
            await self.rtp_server.stop()
        
        logger.info("[MEDIA_GATEWAY] ✅ Service stopped")
    
    async def start_call_session(
        self,
        call_id: str,
        tenant_id: int,
        direction: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Start media session for a call.
        
        Args:
            call_id: Unique call identifier
            tenant_id: Business/tenant ID
            direction: Call direction (inbound/outbound)
            metadata: Optional call metadata
        """
        logger.info(f"[MEDIA_GATEWAY] Starting session: call_id={call_id}, tenant={tenant_id}")
        
        from server.services.media_gateway.call_session import CallSession
        
        session = CallSession(
            call_id=call_id,
            tenant_id=tenant_id,
            direction=direction,
            openai_api_key=self.openai_api_key,
            metadata=metadata or {}
        )
        
        await session.start()
        
        self.active_sessions[call_id] = session
        
        logger.info(f"[MEDIA_GATEWAY] ✅ Session started: {call_id}")
    
    async def end_call_session(self, call_id: str):
        """
        End media session for a call.
        
        Args:
            call_id: Unique call identifier
        """
        session = self.active_sessions.pop(call_id, None)
        
        if session:
            logger.info(f"[MEDIA_GATEWAY] Ending session: {call_id}")
            await session.stop()
            logger.info(f"[MEDIA_GATEWAY] ✅ Session ended: {call_id}")
        else:
            logger.warning(f"[MEDIA_GATEWAY] Session not found: {call_id}")
    
    async def _handle_rtp_packet(self, packet: bytes, source_addr: tuple):
        """
        Handle incoming RTP packet from Asterisk.
        
        Args:
            packet: RTP packet data
            source_addr: Source IP and port
        """
        # Extract RTP payload and forward to appropriate session
        # (Implementation in rtp_server.py handles RTP parsing)
        pass


# Standalone service runner
async def main():
    """Run Media Gateway as standalone service."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    
    gateway = MediaGatewayService()
    
    try:
        await gateway.start()
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await gateway.stop()


if __name__ == "__main__":
    asyncio.run(main())
