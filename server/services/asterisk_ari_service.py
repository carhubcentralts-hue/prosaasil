"""
Asterisk ARI Service - WebSocket event handler and call session manager
Manages call lifecycle, media bridges, and recording for Asterisk calls
"""
import os
import json
import logging
import asyncio
import websockets
import threading
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AsteriskARIService:
    """
    Asterisk ARI event handler and call session manager.
    
    Responsibilities:
    - Listen to ARI WebSocket events (StasisStart, ChannelHangup, etc.)
    - Manage call sessions (create bridges, attach media channels)
    - Trigger internal API calls for call lifecycle
    - Handle recording references
    - Monitor call status transitions
    """
    
    def __init__(
        self,
        ari_url: Optional[str] = None,
        ari_username: Optional[str] = None,
        ari_password: Optional[str] = None,
        stasis_app: str = "prosaas_ai",
        media_gateway_host: Optional[str] = None,
        media_gateway_port: int = 10000
    ):
        """
        Initialize ARI service.
        
        Args:
            ari_url: Asterisk ARI base URL
            ari_username: ARI username
            ari_password: ARI password
            stasis_app: Stasis application name
            media_gateway_host: Media Gateway hostname/IP
            media_gateway_port: Media Gateway RTP port
        """
        self.ari_url = ari_url or os.getenv("ASTERISK_ARI_URL", "http://localhost:8088/ari")
        self.ari_username = ari_username or os.getenv("ASTERISK_ARI_USER", "asterisk")
        self.ari_password = ari_password or os.getenv("ASTERISK_ARI_PASSWORD", "asterisk")
        self.stasis_app = stasis_app
        
        self.media_gateway_host = media_gateway_host or os.getenv("MEDIA_GATEWAY_HOST", "media-gateway")
        self.media_gateway_port = media_gateway_port
        
        # Active call sessions: {channel_id: session_data}
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Event loop control
        self._running = False
        self._ws_task: Optional[asyncio.Task] = None
        
        logger.info(f"[ARI] Initialized service: app={self.stasis_app}, gateway={self.media_gateway_host}:{self.media_gateway_port}")
    
    def start(self):
        """Start ARI event listener in background thread."""
        if self._running:
            logger.warning("[ARI] Service already running")
            return
        
        self._running = True
        
        # Start event loop in separate thread
        thread = threading.Thread(
            target=self._run_event_loop,
            daemon=True,
            name="ARI-EventLoop"
        )
        thread.start()
        
        logger.info("[ARI] Service started")
    
    def stop(self):
        """Stop ARI event listener."""
        self._running = False
        logger.info("[ARI] Service stopped")
    
    def _run_event_loop(self):
        """Run asyncio event loop in thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._listen_to_events())
        except Exception as e:
            logger.error(f"[ARI] Event loop error: {e}")
        finally:
            loop.close()
    
    async def _listen_to_events(self):
        """
        Listen to ARI WebSocket events.
        
        Connects to ARI WebSocket and processes events:
        - StasisStart: New call entering application
        - ChannelHangupRequest: Call is being hung up
        - StasisEnd: Call left application
        """
        ws_url = self.ari_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/events?app={self.stasis_app}&api_key={self.ari_username}:{self.ari_password}"
        
        logger.info(f"[ARI] Connecting to WebSocket: {ws_url}")
        
        while self._running:
            try:
                async with websockets.connect(ws_url) as websocket:
                    logger.info("[ARI] ✅ WebSocket connected")
                    
                    while self._running:
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(),
                                timeout=5.0
                            )
                            
                            event = json.loads(message)
                            await self._handle_event(event)
                            
                        except asyncio.TimeoutError:
                            # Timeout is normal, just continue
                            continue
                        except websockets.ConnectionClosed:
                            logger.warning("[ARI] WebSocket closed, reconnecting...")
                            break
                            
            except Exception as e:
                logger.error(f"[ARI] WebSocket error: {e}")
                if self._running:
                    await asyncio.sleep(5)  # Wait before reconnect
    
    async def _handle_event(self, event: Dict[str, Any]):
        """
        Handle ARI event.
        
        Args:
            event: ARI event data
        """
        event_type = event.get("type")
        
        if event_type == "StasisStart":
            await self._handle_stasis_start(event)
        elif event_type == "ChannelHangupRequest":
            await self._handle_hangup_request(event)
        elif event_type == "StasisEnd":
            await self._handle_stasis_end(event)
        elif event_type == "ChannelStateChange":
            await self._handle_state_change(event)
        else:
            logger.debug(f"[ARI] Unhandled event: {event_type}")
    
    async def _handle_stasis_start(self, event: Dict[str, Any]):
        """
        Handle StasisStart event (call entering application).
        
        Flow:
        1. Extract call metadata from channel variables
        2. Create bridge for call
        3. Add SIP channel to bridge
        4. Create ExternalMedia channel to Media Gateway
        5. Add ExternalMedia to bridge
        6. Call internal API to start call session
        """
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        channel_name = channel.get("name", "")
        
        logger.info(f"[ARI] StasisStart: channel_id={channel_id}, name={channel_name}")
        
        # Extract metadata from channel variables
        variables = channel.get("channelvars", {})
        tenant_id = variables.get("TENANT_ID", "1")
        direction = variables.get("DIRECTION", "inbound")
        lead_id = variables.get("LEAD_ID", "")
        
        caller = channel.get("caller", {})
        connected = channel.get("connected", {})
        from_number = caller.get("number", "")
        to_number = connected.get("number", "")
        
        try:
            # Create bridge for this call
            bridge_id = await self._create_bridge(channel_id)
            
            # Add SIP channel to bridge
            await self._add_channel_to_bridge(channel_id, bridge_id)
            
            # Create ExternalMedia channel to Media Gateway
            external_channel_id = await self._create_external_media(channel_id, bridge_id)
            
            # Store session data
            self.active_sessions[channel_id] = {
                "channel_id": channel_id,
                "bridge_id": bridge_id,
                "external_channel_id": external_channel_id,
                "tenant_id": tenant_id,
                "direction": direction,
                "from_number": from_number,
                "to_number": to_number,
                "lead_id": lead_id,
                "started_at": datetime.utcnow().isoformat()
            }
            
            # Call internal API to start call session
            await self._notify_call_start(channel_id, tenant_id, direction, from_number, to_number, lead_id)
            
            logger.info(f"[ARI] ✅ Call session created: {channel_id}")
            
        except Exception as e:
            logger.error(f"[ARI] ❌ Failed to handle StasisStart: {e}")
            # Cleanup on error
            # TODO: Hangup channel if setup failed
    
    async def _create_bridge(self, channel_id: str) -> str:
        """Create mixing bridge for call."""
        import aiohttp
        
        url = f"{self.ari_url}/bridges"
        auth = aiohttp.BasicAuth(self.ari_username, self.ari_password)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                auth=auth,
                json={"type": "mixing", "name": f"bridge_{channel_id}"}
            ) as response:
                response.raise_for_status()
                bridge_data = await response.json()
                bridge_id = bridge_data["id"]
                
                logger.info(f"[ARI] Created bridge: {bridge_id}")
                return bridge_id
    
    async def _add_channel_to_bridge(self, channel_id: str, bridge_id: str):
        """Add channel to bridge."""
        import aiohttp
        
        url = f"{self.ari_url}/bridges/{bridge_id}/addChannel"
        auth = aiohttp.BasicAuth(self.ari_username, self.ari_password)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                auth=auth,
                params={"channel": channel_id}
            ) as response:
                response.raise_for_status()
                logger.info(f"[ARI] Added channel {channel_id} to bridge {bridge_id}")
    
    async def _create_external_media(self, channel_id: str, bridge_id: str) -> str:
        """
        Create ExternalMedia channel connected to Media Gateway.
        
        ExternalMedia channels send/receive RTP to/from external host.
        """
        import aiohttp
        
        url = f"{self.ari_url}/channels/externalMedia"
        auth = aiohttp.BasicAuth(self.ari_username, self.ari_password)
        
        # ExternalMedia configuration
        external_host = f"{self.media_gateway_host}:{self.media_gateway_port}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                auth=auth,
                json={
                    "app": self.stasis_app,
                    "external_host": external_host,
                    "format": "ulaw",  # g711 ulaw
                    "channelId": f"external_{channel_id}",
                    "variables": {
                        "PARENT_CHANNEL": channel_id
                    }
                }
            ) as response:
                response.raise_for_status()
                external_channel = await response.json()
                external_channel_id = external_channel["id"]
                
                logger.info(f"[ARI] Created ExternalMedia channel: {external_channel_id}")
                
                # Add to bridge
                await self._add_channel_to_bridge(external_channel_id, bridge_id)
                
                return external_channel_id
    
    async def _notify_call_start(
        self,
        call_id: str,
        tenant_id: str,
        direction: str,
        from_number: str,
        to_number: str,
        lead_id: str
    ):
        """
        Notify backend that call has started.
        
        Calls internal API endpoint to create CallLog and start media session.
        """
        import aiohttp
        
        backend_url = os.getenv("BACKEND_URL", "http://localhost:5000")
        url = f"{backend_url}/internal/calls/start"
        
        payload = {
            "call_id": call_id,
            "tenant_id": tenant_id,
            "direction": direction,
            "from_number": from_number,
            "to_number": to_number,
            "lead_id": lead_id if lead_id else None,
            "provider": "asterisk"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"[ARI] ✅ Backend notified of call start: {call_id}")
                    else:
                        logger.warning(f"[ARI] Backend notification failed: status={response.status}")
        except Exception as e:
            logger.error(f"[ARI] Failed to notify backend: {e}")
    
    async def _handle_hangup_request(self, event: Dict[str, Any]):
        """Handle ChannelHangupRequest event."""
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        
        logger.info(f"[ARI] ChannelHangupRequest: {channel_id}")
        
        # Cleanup will happen in StasisEnd
    
    async def _handle_stasis_end(self, event: Dict[str, Any]):
        """
        Handle StasisEnd event (call leaving application).
        
        Cleanup call session and notify backend.
        """
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        
        logger.info(f"[ARI] StasisEnd: {channel_id}")
        
        # Get session data
        session = self.active_sessions.pop(channel_id, None)
        
        if session:
            # Close media stream
            # (Media Gateway handles RTP cleanup)
            
            # Recording is already being captured by MixMonitor
            # It will be processed after call ends
            
            # Notify backend of call end
            await self._notify_call_end(channel_id)
            
            logger.info(f"[ARI] ✅ Call session cleaned up: {channel_id}")
        else:
            logger.warning(f"[ARI] Session not found for {channel_id}")
    
    async def _handle_state_change(self, event: Dict[str, Any]):
        """Handle ChannelStateChange event."""
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        state = channel.get("state")
        
        logger.debug(f"[ARI] ChannelStateChange: {channel_id} -> {state}")
        
        # Update session state if needed
        if channel_id in self.active_sessions:
            self.active_sessions[channel_id]["state"] = state
    
    async def _notify_call_end(self, call_id: str):
        """Notify backend that call has ended."""
        import aiohttp
        
        backend_url = os.getenv("BACKEND_URL", "http://localhost:5000")
        url = f"{backend_url}/internal/calls/end"
        
        payload = {
            "call_id": call_id,
            "provider": "asterisk"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"[ARI] ✅ Backend notified of call end: {call_id}")
                    else:
                        logger.warning(f"[ARI] Backend end notification failed: status={response.status}")
        except Exception as e:
            logger.error(f"[ARI] Failed to notify backend of call end: {e}")
