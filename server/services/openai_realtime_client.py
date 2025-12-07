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
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini-realtime-preview"):
        """
        Initialize Realtime API client
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4o-mini-realtime-preview for cost efficiency)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required")
        
        self.model = model
        self.ws = None
        self.url = f"wss://api.openai.com/v1/realtime?model={model}"
        
        # 🔥 BUILD 318: COST OPTIMIZATION - Instruction caching
        # Track last sent instructions to avoid redundant session.update calls
        self._last_instructions_hash = None
        self._last_voice = None
        self._session_update_count = 0
        
        if websockets is None:
            raise ImportError("websockets library is required. Install with: pip install websockets")
    
    async def connect(self, max_retries: int = 3, backoff_base: float = 1.0):
        """
        Connect to OpenAI Realtime API with retry/backoff
        
        BUILD 168.3: Added reconnection logic for production stability
        
        Args:
            max_retries: Maximum connection attempts (default: 3)
            backoff_base: Base delay in seconds for exponential backoff
        
        Returns:
            WebSocket connection object
        """
        # Close existing connection if present
        if self.ws is not None:
            await self.disconnect()
        
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                self.ws = await websockets.connect(
                    self.url,
                    additional_headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "OpenAI-Beta": "realtime=v1"
                    },
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5
                )
                # 🔥 BUILD 331: Clear logging when WebSocket opens
                logger.info(f"[REALTIME] Connected (attempt {attempt}/{max_retries})")
                print(f"🟢 REALTIME_WS_OPEN model={self.model}")
                return self.ws
                
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    delay = backoff_base * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(f"[REALTIME] Connection attempt {attempt} failed: {e}, retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[REALTIME] All {max_retries} connection attempts failed")
        
        raise last_error or RuntimeError("Connection failed")
    
    async def disconnect(self, reason: str = "normal"):
        """Close WebSocket connection and cleanup session"""
        if self.ws:
            try:
                # 🧹 COST SAFETY: Explicitly close connection to prevent session reuse
                await self.ws.close()
                logger.info("✅ WebSocket connection closed cleanly")
                # 🔥 BUILD 331: Clear logging when WebSocket closes
                print(f"🔴 REALTIME_WS_CLOSED reason={reason}")
            except Exception as e:
                logger.warning(f"⚠️ Error during disconnect: {e}")
                print(f"🔴 REALTIME_WS_CLOSED reason=error:{e}")
            finally:
                self.ws = None
                logger.info("🔌 Disconnected from Realtime API (session destroyed)")
    
    async def send_event(self, event: Dict[str, Any], max_retries: int = 2):
        """
        Send an event to Realtime API with retry
        
        BUILD 168.3: Added retry logic for production stability
        
        Args:
            event: Event dictionary (e.g., {"type": "session.update", ...})
            max_retries: Maximum send attempts for non-audio events
        """
        if not self.ws:
            raise RuntimeError("Not connected. Call connect() first.")
        
        event_type = event.get("type", "unknown")
        is_audio = event_type == "input_audio_buffer.append"
        retries = 1 if is_audio else max_retries  # Audio: no retry (real-time), other: retry
        
        last_error = None
        for attempt in range(retries):
            try:
                message = json.dumps(event)
                await self.ws.send(message)
                return  # Success
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    await asyncio.sleep(0.1)  # Brief delay before retry
                    
        # Log only important failures (not audio drops)
        if not is_audio and last_error:
            logger.error(f"[REALTIME] Send failed after {retries} attempts: {event_type}")
        
        if last_error:
            raise last_error
    
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
        voice: str = "coral",  # 🔥 BUILD 205: Upgraded to 'coral' - better for Hebrew
        input_audio_format: str = "g711_ulaw",
        output_audio_format: str = "g711_ulaw",
        vad_threshold: float = 0.85,  # 🔥 BUILD 206: 0.85 - balanced for Hebrew telephony
        silence_duration_ms: int = 450,  # 🔥 BUILD 206: 450ms - telephony sweet spot (300-500ms range)
        temperature: float = 0.18,
        max_tokens: int = 300,
        transcription_prompt: str = ""  # 🔥 BUILD 202: Dynamic prompt for better Hebrew STT
    ):
        """
        Configure Realtime API session
        
        ✅ REQUIRED: Internal transcription enabled (mandatory for AI to hear audio)
        
        Args:
            instructions: System prompt for the AI
            voice: Voice to use (coral, sage, verse, ash, ballad, alloy, shimmer, echo)
            input_audio_format: Audio format from Twilio (g711_ulaw, pcm16)
            output_audio_format: Audio format to Twilio (g711_ulaw, pcm16)
            vad_threshold: Voice activity detection threshold (0-1)
            silence_duration_ms: Silence duration to detect end of speech
            temperature: AI temperature (0.18-0.25 for Agent 3 spec)
            max_tokens: Maximum tokens (280-320 for Agent 3 spec)
            transcription_prompt: Dynamic prompt with business-specific vocab for better Hebrew STT
        """
        # 🔥 BUILD 202: TRANSCRIPTION IMPROVEMENTS FOR HEBREW
        # - Use gpt-4o-transcribe model (better than whisper-1 for Hebrew)
        # - Add dynamic prompt with business vocabulary (names, cities, services)
        # - Explicit Hebrew language setting
        transcription_config = {
            "model": "gpt-4o-transcribe",  # 🔥 BUILD 202: Better Hebrew accuracy than whisper-1
            "language": "he"  # 🔥 Explicit Hebrew - mandatory for accuracy!
        }
        
        # Add transcription prompt if provided (business-specific vocabulary)
        if transcription_prompt:
            transcription_config["prompt"] = transcription_prompt
            logger.info(f"🎤 [STT PROMPT] Using dynamic transcription prompt ({len(transcription_prompt)} chars)")
        
        # ✅ CRITICAL: Internal transcription is REQUIRED for AI to hear audio!
        # Without input_audio_transcription, the AI receives no STT events and stays silent.
        session_config = {
            "instructions": instructions,
            "modalities": ["audio", "text"],
            "voice": voice,
            "input_audio_format": input_audio_format,
            "output_audio_format": output_audio_format,
            # ✅ MANDATORY: Internal transcription for audio comprehension
            # DO NOT remove this - AI will be completely silent without it!
            "input_audio_transcription": transcription_config,
            # 🔥 BUILD 202: Removed prefix_padding_ms - not supported by SDK, caused crashes
            "turn_detection": {
                "type": "server_vad",
                "threshold": vad_threshold,
                "silence_duration_ms": silence_duration_ms
            },
            "temperature": temperature,  # Agent 3: Allow low temps like 0.18 for focused responses
            "max_response_output_tokens": max_tokens
        }
        
        # 🔍 VERIFICATION LOG: Model configuration for Agent 3 compliance
        logger.info(f"🎯 [REALTIME CONFIG] model={self.model}, stt=gpt-4o-transcribe, temp={temperature}, max_tokens={max_tokens}")
        
        # 🚫 NO TOOLS for phone calls - appointment scheduling via NLP only
        
        # For g711_ulaw, sample rate is always 8000 Hz (telephony standard)
        # No need to explicitly set it - it's implicit in the format
        
        # 🔥 BUILD 318: INSTRUCTION CACHING - Skip if same instructions already sent
        # This prevents redundant session.update calls that cost $11+ in text input!
        import hashlib
        instructions_hash = hashlib.md5(instructions.encode()).hexdigest()[:16]
        
        if self._last_instructions_hash == instructions_hash and self._last_voice == voice:
            logger.info(f"💰 [COST SAVE] Skipping session.update - same instructions already sent (hash={instructions_hash})")
            return
        
        self._last_instructions_hash = instructions_hash
        self._last_voice = voice
        self._session_update_count += 1
        
        # 🔥 BUILD 332: COST ALERT - Warn if session.update exceeds expected baseline
        if self._session_update_count > 2:
            logger.warning(f"⚠️ [COST ALERT] Session update #{self._session_update_count} exceeds expected baseline of 2! Check for prompt regeneration loop!")
            print(f"⚠️ [BUILD 332] COST ALERT: session.update called {self._session_update_count} times (expected ≤2)")
        else:
            logger.info(f"✅ [BUILD 318] Session update #{self._session_update_count} (instructions changed, hash={instructions_hash})")
        await self.send_event({
            "type": "session.update",
            "session": session_config
        })
        logger.info(f"✅ Session configured: voice={voice}, format={input_audio_format}, vad_threshold={vad_threshold}, transcription=gpt-4o-transcribe")
