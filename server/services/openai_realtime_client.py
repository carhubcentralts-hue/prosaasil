"""
OpenAI Realtime API Client
WebSocket client for low-latency speech-to-speech conversations
"""
import os
import json
import asyncio
import logging
from typing import AsyncIterator, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    import websockets
else:
    try:
        import websockets
    except ImportError:
        websockets = None  # type: ignore

logger = logging.getLogger(__name__)

OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"


class OpenAIRealtimeClient:
    """
    WebSocket client for OpenAI Realtime API
    
    Usage:
        client = OpenAIRealtimeClient()
        await client.connect()
        await client.send_event({"type": "session.update", ...})
        async for event in client.recv_events():
            print(event)
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-realtime-preview"):
        """
        Initialize Realtime API client
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4o-realtime-preview)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required")
        
        self.model = model
        self.ws = None
        self.url = f"wss://api.openai.com/v1/realtime?model={model}"
        
        if websockets is None:
            raise ImportError("websockets library is required. Install with: pip install websockets")
    
    async def connect(self):
        """
        Connect to OpenAI Realtime API
        
        🚨 COST SAFETY: Always creates a fresh session (no reuse)
        
        Returns:
            WebSocket connection object
        """
        # 🚨 CRITICAL: NEVER reuse connections - always create fresh session
        if self.ws is not None:
            logger.warning("⚠️ Existing connection found - closing it first (prevent session reuse)")
            await self.disconnect()
        
        logger.info(f"[CALL DEBUG] 🔌 Connecting to OpenAI Realtime API: {self.model}")
        logger.info(f"[CALL DEBUG] URL: {self.url}")
        logger.info(f"[CALL DEBUG] API key present: {bool(self.api_key)}, key_prefix: {self.api_key[:10] if self.api_key else 'N/A'}...")
        # 🔥 CRITICAL: Force print to bypass any suppression
        print(f"🔌 [CALL DEBUG] Connecting to OpenAI: model={self.model}, api_key_present={bool(self.api_key)}", flush=True)
        
        try:
            self.ws = await websockets.connect(
                self.url,
                additional_headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "OpenAI-Beta": "realtime=v1"
                },
                ping_interval=20,
                ping_timeout=10
            )
            logger.info("[CALL DEBUG] ✅ Connected to OpenAI Realtime API (FRESH SESSION)")
            return self.ws
            
        except Exception as e:
            logger.error(f"[CALL DEBUG] ❌ Failed to connect to Realtime API: {e}")
            import traceback
            logger.error(f"[CALL DEBUG] Traceback: {traceback.format_exc()}")
            raise
    
    async def disconnect(self):
        """Close WebSocket connection and cleanup session"""
        if self.ws:
            try:
                # 🧹 COST SAFETY: Explicitly close connection to prevent session reuse
                await self.ws.close()
                logger.info("✅ WebSocket connection closed cleanly")
            except Exception as e:
                logger.warning(f"⚠️ Error during disconnect: {e}")
            finally:
                self.ws = None
                logger.info("🔌 Disconnected from Realtime API (session destroyed)")
    
    async def send_event(self, event: Dict[str, Any]):
        """
        Send an event to Realtime API
        
        Args:
            event: Event dictionary (e.g., {"type": "session.update", ...})
        """
        if not self.ws:
            raise RuntimeError("Not connected. Call connect() first.")
        
        try:
            message = json.dumps(event)
            await self.ws.send(message)
            
            # Log important events (not audio chunks)
            if event.get("type") != "input_audio_buffer.append":
                logger.debug(f"📤 Sent: {event.get('type')}")
                
        except Exception as e:
            logger.error(f"❌ Error sending event: {e}")
            raise
    
    async def recv_events(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Receive events from Realtime API (async generator)
        
        Yields:
            Event dictionaries from the API
        """
        if not self.ws:
            raise RuntimeError("Not connected. Call connect() first.")
        
        try:
            async for raw in self.ws:
                try:
                    event = json.loads(raw)
                    
                    # Log important events (not audio deltas)
                    event_type = event.get("type", "")
                    
                    # 🎯 TASK 1: Log audio chunks from OpenAI
                    if event_type == "response.audio.delta":
                        audio_b64 = event.get("delta", "")
                        if audio_b64:
                            import base64
                            chunk_bytes = base64.b64decode(audio_b64)
                            logger.info(
                                "[REALTIME] got audio chunk from OpenAI: bytes=%d",
                                len(chunk_bytes)
                            )
                    
                    if not event_type.endswith(".delta"):
                        logger.debug(f"📥 Received: {event_type}")
                    
                    yield event
                    
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Invalid JSON from Realtime API: {e}")
                    continue
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"⚠️ Realtime API connection closed: {e}")
        except Exception as e:
            logger.error(f"❌ Error receiving events: {e}")
            raise
    
    async def send_audio_chunk(self, audio_base64: str):
        """
        Send audio chunk to Realtime API
        
        Args:
            audio_base64: Base64-encoded audio data
        """
        await self.send_event({
            "type": "input_audio_buffer.append",
            "audio": audio_base64
        })
    
    async def commit_audio_buffer(self):
        """Commit audio buffer (end of user utterance)"""
        await self.send_event({
            "type": "input_audio_buffer.commit"
        })
    
    async def clear_audio_buffer(self):
        """Clear audio buffer (e.g., on barge-in)"""
        await self.send_event({
            "type": "input_audio_buffer.clear"
        })
    
    async def cancel_response(self):
        """Cancel current AI response (e.g., on barge-in)"""
        await self.send_event({
            "type": "response.cancel"
        })
    
    async def send_user_message(self, text: str):
        """
        Send a user message (e.g., DTMF input) to the AI
        
        Args:
            text: User's text input (e.g., from DTMF)
        """
        # Add user message to conversation
        await self.send_event({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": text
                }]
            }
        })
        
        # Trigger response generation
        await self.send_event({
            "type": "response.create"
        })
        
        logger.info(f"✅ User message sent: '{text[:50]}...'")
    
    async def send_text_response(self, text: str):
        """
        Send a text response that will be spoken by the AI
        
        Args:
            text: Text to be converted to speech and spoken
        """
        # Add assistant message to conversation
        await self.send_event({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "assistant",
                "content": [{
                    "type": "text",
                    "text": text
                }]
            }
        })
        
        # Trigger response generation
        await self.send_event({
            "type": "response.create"
        })
        
        logger.info(f"✅ Text response sent: '{text[:50]}...'")
    
    async def configure_session(
        self,
        instructions: str,
        voice: str = "alloy",
        input_audio_format: str = "g711_ulaw",
        output_audio_format: str = "g711_ulaw",
        vad_threshold: float = 0.6,
        silence_duration_ms: int = 500,
        temperature: float = 0.18,
        max_tokens: int = 300
    ):
        """
        Configure Realtime API session
        
        ✅ REQUIRED: Internal Whisper transcription enabled (mandatory for AI to hear audio)
        
        Args:
            instructions: System prompt for the AI
            voice: Voice to use (alloy, echo, shimmer, verse, ash, ballad)
            input_audio_format: Audio format from Twilio (g711_ulaw, pcm16)
            output_audio_format: Audio format to Twilio (g711_ulaw, pcm16)
            vad_threshold: Voice activity detection threshold (0-1)
            silence_duration_ms: Silence duration to detect end of speech
            temperature: AI temperature (0.18-0.25 for Agent 3 spec)
            max_tokens: Maximum tokens (280-320 for Agent 3 spec)
        """
        # ✅ CRITICAL: Internal transcription is REQUIRED for AI to hear audio!
        # Without input_audio_transcription, the AI receives no STT events and stays silent.
        # This is NOT the same as "logging transcription" - it's the core audio→text pipeline.
        session_config = {
            "instructions": instructions,
            "modalities": ["audio", "text"],
            "voice": voice,
            "input_audio_format": input_audio_format,
            "output_audio_format": output_audio_format,
            # ✅ MANDATORY: Internal Whisper transcription for audio comprehension
            # DO NOT remove this - AI will be completely silent without it!
            "input_audio_transcription": {
                "model": "whisper-1"
                # Auto-detect language (Hebrew specified in system prompt)
            },
            "turn_detection": {
                "type": "server_vad",
                "threshold": vad_threshold,
                "silence_duration_ms": silence_duration_ms,
                "prefix_padding_ms": 300
            },
            "temperature": temperature,  # Agent 3: Allow low temps like 0.18 for focused responses
            "max_response_output_tokens": max_tokens
        }
        
        # 🔍 VERIFICATION LOG: Model configuration for Agent 3 compliance
        logger.info(f"🎯 [REALTIME CONFIG] model=gpt-4o-realtime-preview, temp={temperature}, max_tokens={max_tokens}")
        
        # 🚫 NO TOOLS for phone calls - appointment scheduling via NLP only
        
        # For g711_ulaw, sample rate is always 8000 Hz (telephony standard)
        # No need to explicitly set it - it's implicit in the format
        
        logger.info(f"✅ Configuring session WITH internal transcription (required for functionality)")
        await self.send_event({
            "type": "session.update",
            "session": session_config
        })
        logger.info(f"✅ Session configured: voice={voice}, format={input_audio_format}, vad_threshold={vad_threshold}, transcription=ENABLED (whisper-1)")
