"""
Call Session - Manages media streaming for a single call
Bridges RTP (Asterisk) with OpenAI Realtime WebSocket
"""
import asyncio
import logging
import json
import base64
from typing import Dict, Any, Optional, Tuple
from server.services.media_gateway.rtp_server import RTPSession, RTPPacket
from server.services.media_gateway.audio_codec import AudioCodec, AudioFrameBuffer, BYTES_PER_FRAME_ULAW
from server.services.call_state_machine import CallStateMachine, CallState, HangupReason
import websockets

logger = logging.getLogger(__name__)


class CallSession:
    """
    Media session for a single call.
    
    Responsibilities:
    - Manage RTP session with Asterisk
    - Connect to OpenAI Realtime WebSocket
    - Convert audio formats (g711 ulaw <-> PCM16 24kHz)
    - Handle barge-in (no buffering delays)
    - Ensure clean cleanup of all resources
    """
    
    def __init__(
        self,
        call_id: str,
        tenant_id: int,
        direction: str,
        openai_api_key: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize call session.
        
        Args:
            call_id: Unique call identifier
            tenant_id: Business/tenant ID
            direction: Call direction (inbound/outbound)
            openai_api_key: OpenAI API key
            metadata: Optional call metadata
        """
        self.call_id = call_id
        self.tenant_id = tenant_id
        self.direction = direction
        self.openai_api_key = openai_api_key
        self.metadata = metadata or {}
        
        # State machine for explicit lifecycle tracking
        self.state_machine = CallStateMachine(call_id)
        
        # RTP session (created when remote address known)
        self.rtp_session: Optional[RTPSession] = None
        self.remote_addr: Optional[Tuple[str, int]] = None
        
        # OpenAI Realtime WebSocket
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.ws_task: Optional[asyncio.Task] = None
        
        # Audio buffers
        self.inbound_buffer = AudioFrameBuffer(BYTES_PER_FRAME_ULAW)
        
        # Codec converter
        self.codec = AudioCodec()
        
        # Control flags
        self.running = False
        
        logger.info(f"[CALL_SESSION] {call_id}: Created session (tenant={tenant_id}, direction={direction})")
    
    async def start(self):
        """Start call session."""
        logger.info(f"[CALL_SESSION] {self.call_id}: Starting session")
        
        self.running = True
        
        # Transition to RINGING state
        self.state_machine.transition_to(CallState.RINGING, "session_start")
        
        # Connect to OpenAI Realtime
        await self._connect_openai_realtime()
        
        # Start audio processing loop
        self.ws_task = asyncio.create_task(self._audio_processing_loop())
        
        logger.info(f"[CALL_SESSION] {self.call_id}: ✅ Session started")
    
    async def stop(self):
        """Stop call session and cleanup all resources."""
        logger.info(f"[CALL_SESSION] {self.call_id}: Stopping session")
        
        # Request cleanup (ensures this runs exactly once)
        if not self.state_machine.request_cleanup():
            logger.warning(f"[CALL_SESSION] {self.call_id}: Cleanup already in progress")
            return
        
        self.running = False
        
        # Cancel audio processing task
        if self.ws_task:
            self.ws_task.cancel()
            try:
                await self.ws_task
            except asyncio.CancelledError:
                pass
        
        # Close OpenAI WebSocket
        if self.ws:
            try:
                await self.ws.close()
                logger.debug(f"[CALL_SESSION] {self.call_id}: WebSocket closed")
            except Exception as e:
                logger.error(f"[CALL_SESSION] {self.call_id}: Error closing WebSocket: {e}")
        
        # Cleanup RTP session (no explicit close needed, just unregister)
        if self.rtp_session:
            logger.debug(f"[CALL_SESSION] {self.call_id}: RTP session cleanup")
        
        # Mark as completed
        self.state_machine.transition_to(CallState.COMPLETED, "session_stopped")
        
        logger.info(f"[CALL_SESSION] {self.call_id}: ✅ Session stopped")
    
    async def _connect_openai_realtime(self):
        """
        Connect to OpenAI Realtime API WebSocket.
        
        Raises:
            Exception: If connection fails
        """
        # OpenAI Realtime API endpoint
        url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"
        
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        try:
            self.ws = await websockets.connect(url, extra_headers=headers)
            logger.info(f"[CALL_SESSION] {self.call_id}: ✅ Connected to OpenAI Realtime")
            
            # Configure session
            await self._configure_realtime_session()
            
        except Exception as e:
            logger.error(f"[CALL_SESSION] {self.call_id}: Failed to connect to OpenAI: {e}")
            raise
    
    async def _configure_realtime_session(self):
        """Configure OpenAI Realtime session parameters."""
        # Session configuration
        config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": f"You are an AI assistant for call {self.call_id}",
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                }
            }
        }
        
        await self.ws.send(json.dumps(config))
        logger.debug(f"[CALL_SESSION] {self.call_id}: Session configured")
    
    async def _audio_processing_loop(self):
        """
        Main audio processing loop.
        
        Handles:
        - RTP packets from Asterisk → OpenAI
        - OpenAI audio → RTP packets to Asterisk
        - State transitions
        - Cleanup on termination
        """
        try:
            while self.running:
                # Process inbound audio (RTP → OpenAI)
                await self._process_inbound_audio()
                
                # Process outbound audio (OpenAI → RTP)
                await self._process_outbound_audio()
                
                # Check for state transitions
                self._check_state_transitions()
                
                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.001)  # 1ms
                
        except asyncio.CancelledError:
            logger.info(f"[CALL_SESSION] {self.call_id}: Audio processing cancelled")
        except Exception as e:
            logger.error(f"[CALL_SESSION] {self.call_id}: Audio processing error: {e}")
            self.state_machine.mark_hangup(HangupReason.SYSTEM_ERROR, "audio_loop")
    
    async def _process_inbound_audio(self):
        """Process inbound audio from RTP to OpenAI."""
        if not self.rtp_session or not self.ws:
            return
        
        # Get next audio frame from jitter buffer
        ulaw_frame = self.rtp_session.get_next_audio_frame()
        if not ulaw_frame:
            return
        
        # Convert g711 ulaw (8kHz) to PCM16 (24kHz)
        pcm_frame = self.codec.ulaw_to_pcm24k(ulaw_frame)
        if not pcm_frame:
            logger.warning(f"[CALL_SESSION] {self.call_id}: Failed to convert inbound audio")
            return
        
        # Send to OpenAI (base64 encoded PCM16)
        audio_b64 = base64.b64encode(pcm_frame).decode('utf-8')
        
        message = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        }
        
        try:
            await self.ws.send(json.dumps(message))
        except Exception as e:
            logger.error(f"[CALL_SESSION] {self.call_id}: Failed to send audio to OpenAI: {e}")
    
    async def _process_outbound_audio(self):
        """Process outbound audio from OpenAI to RTP."""
        if not self.rtp_session or not self.ws:
            return
        
        try:
            # Check for messages from OpenAI (non-blocking)
            message = await asyncio.wait_for(self.ws.recv(), timeout=0.001)
            event = json.loads(message)
            
            # Handle audio delta events
            if event.get("type") == "response.audio.delta":
                audio_b64 = event.get("delta", "")
                if audio_b64:
                    # Decode base64 PCM16 (24kHz)
                    pcm_data = base64.b64decode(audio_b64)
                    
                    # Convert PCM16 (24kHz) to g711 ulaw (8kHz)
                    ulaw_data = self.codec.pcm24k_to_ulaw(pcm_data)
                    if not ulaw_data:
                        logger.warning(f"[CALL_SESSION] {self.call_id}: Failed to convert outbound audio")
                        return
                    
                    # Buffer and send as 20ms frames
                    frames = self.inbound_buffer.add_data(ulaw_data)
                    for frame in frames:
                        packet = self.rtp_session.create_outbound_packet(frame)
                        # Send packet via RTP server
                        # (RTP server reference needed - to be added)
                        pass
            
            # Handle other events (conversation item, input audio transcription, etc.)
            elif event.get("type") in ["conversation.item.created", "input_audio_buffer.speech_started"]:
                # Transition to ACTIVE state when conversation starts
                if self.state_machine.current_state == CallState.RINGING:
                    self.state_machine.transition_to(CallState.ACTIVE, "conversation_started")
            
        except asyncio.TimeoutError:
            # No message available, continue
            pass
        except Exception as e:
            logger.error(f"[CALL_SESSION] {self.call_id}: Error processing OpenAI message: {e}")
    
    def _check_state_transitions(self):
        """Check for automatic state transitions (silence, hangup, etc.)."""
        # Check for silence timeout (20s)
        if self.state_machine.current_state == CallState.ACTIVE:
            duration_active = self.state_machine.get_duration_in_state(CallState.ACTIVE)
            if duration_active and duration_active > 20.0:
                # TODO: Check if audio was received in last 20s
                # For now, just log
                logger.debug(f"[CALL_SESSION] {self.call_id}: Active for {duration_active:.1f}s")
    
    def set_rtp_session(self, rtp_session: RTPSession, remote_addr: Tuple[str, int]):
        """
        Attach RTP session to call session.
        
        Args:
            rtp_session: RTP session for this call
            remote_addr: Remote Asterisk address
        """
        self.rtp_session = rtp_session
        self.remote_addr = remote_addr
        logger.info(f"[CALL_SESSION] {self.call_id}: RTP session attached ({remote_addr})")
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of call session state."""
        summary = self.state_machine.get_state_summary()
        summary.update({
            "rtp_connected": self.rtp_session is not None,
            "ws_connected": self.ws is not None and self.ws.open,
            "running": self.running
        })
        
        if self.rtp_session:
            summary["rtp_stats"] = self.rtp_session.get_stats()
        
        return summary
