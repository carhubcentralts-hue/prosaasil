"""
Gemini Realtime API Client
WebSocket client for low-latency speech-to-speech conversations using Gemini Live API

🔥 PRODUCTION LOGGING POLICY:
- IS_PROD (DEBUG=1): Only log session start, first audio chunk, response complete
- DEV (DEBUG=0): Log all events except audio delta spam
- REALTIME_VERBOSE=1: Override - log everything
"""
import os
import json
import asyncio
import logging
import base64
import binascii
import builtins
from typing import AsyncIterator, Optional, Dict, Any, TYPE_CHECKING

try:
    from google import genai
    from google.genai import types
    _genai_available = True
except ImportError:
    genai = None
    types = None
    _genai_available = False

logger = logging.getLogger(__name__)

# Use original print for critical logging (bypasses DEBUG gating)
_orig_print = builtins.print

# Production mode control
IS_PROD = os.getenv("DEBUG", "1") == "1"  # DEBUG=1 means production
REALTIME_VERBOSE = os.getenv("REALTIME_VERBOSE", "0") == "1"  # Explicit verbose flag

# Gemini Live API configuration
# 🔥 CRITICAL: Use native audio model for proper bidirectional audio streaming
# The native-audio-preview model is required for stable audio output in telephony
GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")

# Audio format constants
# Gemini expects 16kHz mono PCM for input, outputs 24kHz mono PCM
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000

# Temperature configuration (Gemini supports 0.0-2.0, unlike OpenAI Realtime)
GEMINI_TEMPERATURE_MIN = 0.0
GEMINI_TEMPERATURE_MAX = 2.0
GEMINI_TEMPERATURE_DEFAULT = 0.6


def _clamp_temperature(requested_temp: Optional[float]) -> float:
    """
    Clamp temperature to Gemini API range (0.0-2.0).
    
    Args:
        requested_temp: The desired temperature value (None for default)
    
    Returns:
        Clamped temperature value (0.0-2.0)
    """
    if requested_temp is None:
        return GEMINI_TEMPERATURE_DEFAULT
    
    if requested_temp < GEMINI_TEMPERATURE_MIN:
        logger.warning(f"⚠️ Temperature {requested_temp} below minimum {GEMINI_TEMPERATURE_MIN}, clamping")
        return GEMINI_TEMPERATURE_MIN
    
    if requested_temp > GEMINI_TEMPERATURE_MAX:
        logger.warning(f"⚠️ Temperature {requested_temp} above maximum {GEMINI_TEMPERATURE_MAX}, clamping")
        return GEMINI_TEMPERATURE_MAX
    
    return requested_temp


def _fix_base64_padding(data: str) -> str:
    """
    Fix base64 padding by adding missing padding characters.
    Base64 strings must have length divisible by 4.
    
    Args:
        data: Base64 encoded string (possibly missing padding)
    
    Returns:
        Base64 string with correct padding
    """
    # Remove any whitespace
    data = data.strip()
    
    # Add padding if needed (base64 strings must be divisible by 4)
    missing_padding = len(data) % 4
    if missing_padding:
        data += '=' * (4 - missing_padding)
    
    return data


def _sanitize_text_for_realtime(text: str, max_chars: int = 8000) -> str:
    """
    Sanitize text for realtime streaming.
    Keep instructions short and conversational for realtime use.
    
    Args:
        text: Text to sanitize
        max_chars: Maximum character limit
    
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Flatten newlines and normalize whitespace
    t = text.replace("\\n", " ").replace("\n", " ")
    t = " ".join(t.split()).strip()
    
    # Truncate if needed
    if max_chars and len(t) > max_chars:
        t = t[:max_chars]
    
    return t


class GeminiRealtimeClient:
    """
    Gemini Live API client for realtime audio streaming
    
    Usage:
        client = GeminiRealtimeClient()
        await client.connect()
        await client.send_audio(audio_bytes)
        async for event in client.recv_events():
            if event['type'] == 'audio':
                play_audio(event['data'])
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = None):
        """
        Initialize Gemini Realtime API client
        
        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
            model: Model to use (default: GEMINI_LIVE_MODEL env var or gemini-2.5-flash-native-audio-preview-12-2025)
        """
        if not _genai_available:
            raise ImportError(
                "google-genai library is required for Gemini Live API. "
                "Install with: pip install google-genai"
            )
        
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required")
        
        self.model = model or GEMINI_LIVE_MODEL
        self.session = None
        self._session_cm = None  # Store context manager for proper cleanup
        self.client = None
        self._connected = False
        
        # Track session state
        self._last_instructions_hash = None
        self._session_update_count = 0
    
    async def connect(
        self,
        system_instructions: Optional[str] = None,
        temperature: Optional[float] = None,
        voice_id: Optional[str] = None,
        max_retries: int = 3,
        backoff_base: float = 1.0
    ):
        """
        Connect to Gemini Live API with retry/backoff
        
        Args:
            system_instructions: System prompt for the conversation
            temperature: Temperature for generation (0.0-2.0)
            voice_id: Voice ID to use (Gemini voice name)
            max_retries: Maximum connection attempts
            backoff_base: Base delay in seconds for exponential backoff
        
        Returns:
            Session object
        """
        if self._connected and self.session:
            await self.disconnect()
        
        # Initialize client if needed
        if not self.client:
            self.client = genai.Client(api_key=self.api_key)
        
        # Prepare configuration
        temp = _clamp_temperature(temperature)
        
        # Build config for Gemini Live API
        config = {
            "response_modalities": ["AUDIO"],  # Request audio output
            "generation_config": {
                "temperature": temp,
            }
        }
        
        # 🔥 FIX 3: Explicitly disable tool use to prevent function_call issues
        # Ensure no tools are configured in the session
        # Note: Even without tools config, Gemini might infer function calls from prompts
        # So we also add explicit instruction in system_instructions
        
        # Add system instructions if provided
        if system_instructions:
            sanitized_instructions = _sanitize_text_for_realtime(system_instructions)
            # Append explicit "no tools" instruction
            sanitized_instructions += "\n\nIMPORTANT: You do NOT have access to any tools or functions. Never attempt to call any functions. Always respond directly with audio only."
            config["system_instruction"] = sanitized_instructions
        else:
            # Even without system instructions, add the no-tools instruction
            config["system_instruction"] = "IMPORTANT: You do NOT have access to any tools or functions. Never attempt to call any functions. Always respond directly with audio only."
        
        # Add voice if provided
        if voice_id:
            config["speech_config"] = {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": voice_id
                    }
                }
            }
        
        last_error = None
        for attempt in range(1, max_retries + 1):
            cm = None
            try:
                # Connect to Live API - create context manager
                cm = self.client.aio.live.connect(
                    model=self.model,
                    config=config
                )
                
                # Manually enter the context manager
                session = await cm.__aenter__()
                
                # Store both for later cleanup
                self._session_cm = cm
                self.session = session
                self._connected = True
                
                logger.debug(f"[GEMINI_LIVE] Connected (attempt {attempt}/{max_retries})")
                logger.info(f"🟢 GEMINI_LIVE_WS_OPEN model={self.model}")
                _orig_print(f"🟢 [GEMINI_LIVE] Connected: {self.model}", flush=True)
                
                return self.session
                
            except Exception as e:
                last_error = e
                # Clean up context manager if we failed after creating it
                if cm:
                    try:
                        await cm.__aexit__(None, None, None)
                    except Exception:
                        pass  # Ignore cleanup errors
                
                if attempt < max_retries:
                    delay = backoff_base * (2 ** (attempt - 1))
                    logger.warning(f"[GEMINI_LIVE] Connection attempt {attempt} failed: {e}, retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[GEMINI_LIVE] All {max_retries} connection attempts failed")
        
        raise last_error or RuntimeError("Gemini Live API connection failed")
    
    async def disconnect(self, reason: str = "normal"):
        """Close Live API session and cleanup"""
        if self._session_cm:
            try:
                # Close the context manager properly
                await self._session_cm.__aexit__(None, None, None)
                logger.debug("✅ Gemini Live session closed cleanly")
                logger.info(f"🔴 GEMINI_LIVE_WS_CLOSED reason={reason}")
                _orig_print(f"🔴 [GEMINI_LIVE] Disconnected: {reason}", flush=True)
            except Exception as e:
                logger.warning(f"⚠️ Error during disconnect: {e}")
                logger.error(f"🔴 GEMINI_LIVE_WS_CLOSED reason=error:{e}")
            finally:
                self._session_cm = None
                self.session = None
                self._connected = False
                logger.debug("🔌 Disconnected from Gemini Live API")
        elif self.session:
            # Fallback cleanup if only session exists
            logger.warning("⚠️ Cleaning up session without context manager")
            self.session = None
            self._connected = False
    
    async def send_audio(self, audio_bytes: bytes, end_of_turn: bool = False):
        """
        Send audio data to Gemini Live API
        
        Args:
            audio_bytes: Raw PCM audio data (16-bit, 16kHz, mono)
            end_of_turn: Whether this is the end of user's turn (unused for realtime input)
        """
        if not self._connected or not self.session:
            raise RuntimeError("Not connected. Call connect() first.")
        
        try:
            # Gemini Live API expects audio as a Blob object
            # Create a Blob with the audio data and proper MIME type
            audio_blob = types.Blob(
                data=audio_bytes,
                mime_type="audio/pcm;rate=16000"
            )
            
            # 🔥 LOG: Track audio sent to Gemini
            if not hasattr(self, '_audio_chunks_sent'):
                self._audio_chunks_sent = 0
                logger.info(f"🎤 [GEMINI_SEND] Starting to send audio to Gemini Live API")
            self._audio_chunks_sent += 1
            
            # Log first few chunks for debugging
            if self._audio_chunks_sent <= 3:
                logger.info(f"🎤 [GEMINI_SEND] audio_chunk #{self._audio_chunks_sent}: {len(audio_bytes)} bytes")
            
            # Send audio using send_realtime_input
            # Note: end_of_turn is not used for realtime input (uses VAD instead)
            await self.session.send_realtime_input(audio=audio_blob)
            
        except Exception as e:
            logger.error(f"❌ [GEMINI_SEND] Failed to send audio: {e}")
            logger.exception(f"[GEMINI_THREAD_CRASH] Exception in send_audio", exc_info=True)
            raise
    
    async def send_text(self, text: str, end_of_turn: bool = True):
        """
        Send text message to Gemini Live API
        
        Args:
            text: Text message to send
            end_of_turn: Whether this is the end of user's turn (unused for realtime input)
        """
        if not self._connected or not self.session:
            raise RuntimeError("Not connected. Call connect() first.")
        
        try:
            # 🔥 LOG: Track text sent to Gemini
            if text:
                logger.info(f"📝 [GEMINI_SEND] text: {text[:100]}...")
            else:
                logger.info(f"📝 [GEMINI_SEND] text: (empty - greeting trigger)")
            
            # Send text using send_realtime_input
            # Note: end_of_turn is not used for realtime input (uses VAD instead)
            await self.session.send_realtime_input(text=text)
        except Exception as e:
            logger.error(f"❌ [GEMINI_SEND] Failed to send text: {e}")
            logger.exception(f"[GEMINI_THREAD_CRASH] Exception in send_text", exc_info=True)
            raise
    
    async def update_config(
        self,
        system_instructions: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        """
        Update session configuration
        
        Args:
            system_instructions: New system instructions
            temperature: New temperature value
        """
        if not self._connected or not self.session:
            raise RuntimeError("Not connected. Call connect() first.")
        
        # Note: Gemini Live API may not support mid-session config updates
        # This is a placeholder for future API support
        logger.warning("[GEMINI_LIVE] Config updates during session not yet implemented")
    
    async def recv_events(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Receive events from Gemini Live API (async generator)
        
        🔥 PRODUCTION MODE: Only logs macro events (session start, first audio, completion)
        🔥 DEVELOPMENT MODE: Logs all events except audio delta spam
        🔥 REALTIME_VERBOSE=1: Logs everything including audio deltas
        
        Yields:
            Event dictionaries with structure:
            {
                'type': 'audio' | 'text' | 'function_call' | 'setup_complete' | 'turn_complete' | 'interrupted',
                'data': <event-specific data>,
                'response_id': <optional response ID>
            }
        """
        if not self._connected or not self.session:
            raise RuntimeError("Not connected. Call connect() first.")
        
        # Track first audio chunk for production logging
        _first_audio_logged = False
        _setup_complete_seen = False  # Track if we've already seen setup_complete
        
        try:
            async for server_message in self.session.receive():
                try:
                    # Parse Gemini Live API message structure
                    # 🔥 CRITICAL: Gemini messages can have MULTIPLE attributes!
                    # We must check ALL attributes, not use if/elif
                    # A message can have both setup_complete AND server_content!
                    
                    # 🔥 FIX: Log event keys to verify structure (as requested in problem statement)
                    # This helps debug which attributes Gemini actually sends
                    event_attrs = [attr for attr in dir(server_message) if not attr.startswith('_')]
                    if not IS_PROD or REALTIME_VERBOSE:
                        logger.info(f"[GEMINI_EVENT_KEYS] {event_attrs}")
                    
                    # Check for setup complete (only yield first time)
                    if hasattr(server_message, 'setup_complete') and not _setup_complete_seen:
                        _setup_complete_seen = True
                        event = {
                            'type': 'setup_complete',
                            'data': None
                        }
                        logger.info("✅ [GEMINI_RECV] setup_complete (FIRST)")
                        if not IS_PROD or REALTIME_VERBOSE:
                            logger.info("[GEMINI_LIVE] Setup complete (first occurrence)")
                        yield event
                    
                    # Check for server content (audio/text response)
                    # 🔥 FIX: Changed from elif to if - messages can have multiple attributes!
                    if hasattr(server_message, 'server_content'):
                        content = server_message.server_content
                        
                        # Check if it's audio
                        if hasattr(content, 'model_turn') and content.model_turn:
                            parts = content.model_turn.parts
                            for part in parts:
                                if hasattr(part, 'inline_data'):
                                    # Audio data
                                    inline_data = part.inline_data
                                    # Check if inline_data is not None before accessing mime_type
                                    if inline_data and hasattr(inline_data, 'mime_type') and inline_data.mime_type.startswith('audio/'):
                                        try:
                                            # Decode base64 audio with padding fix
                                            # Fix: Gemini API sometimes sends audio with incorrect padding
                                            fixed_data = _fix_base64_padding(inline_data.data)
                                            audio_bytes = base64.b64decode(fixed_data)
                                            
                                            event = {
                                                'type': 'audio',
                                                'data': audio_bytes,
                                                'mime_type': inline_data.mime_type
                                            }
                                            
                                            # Log first audio chunk in production
                                            if IS_PROD and not REALTIME_VERBOSE and not _first_audio_logged:
                                                _first_audio_logged = True
                                                logger.info(f"🔊 [GEMINI_RECV] audio_chunk (FIRST): {len(audio_bytes)} bytes")
                                                _orig_print(f"🔊 [GEMINI_RECV] audio_chunk (FIRST): {len(audio_bytes)} bytes", flush=True)
                                            elif not IS_PROD or REALTIME_VERBOSE:
                                                logger.debug(f"🔊 [GEMINI_RECV] audio_chunk: {len(audio_bytes)} bytes")
                                            
                                            yield event
                                        except (binascii.Error, ValueError) as audio_decode_error:
                                            # Skip malformed audio chunks gracefully
                                            logger.debug(f"⚠️ [GEMINI_RECV] Skipping malformed audio chunk: {audio_decode_error}")
                                            # Continue processing other parts
                                
                                elif hasattr(part, 'text'):
                                    # Text response
                                    event = {
                                        'type': 'text',
                                        'data': part.text
                                    }
                                    
                                    logger.info(f"📝 [GEMINI_RECV] text: {part.text[:100]}...")
                                    if not IS_PROD or REALTIME_VERBOSE:
                                        logger.info(f"[GEMINI_LIVE] Text response: {part.text[:100]}")
                                    
                                    yield event
                    
                    # Check for turn complete
                    # 🔥 FIX: Changed from elif to if - messages can have multiple attributes!
                    if hasattr(server_message, 'turn_complete'):
                        event = {
                            'type': 'turn_complete',
                            'data': None
                        }
                        
                        logger.info("✅ [GEMINI_RECV] turn_complete")
                        if not IS_PROD or REALTIME_VERBOSE:
                            logger.info("[GEMINI_LIVE] Turn complete")
                        
                        # Reset first audio flag for next response
                        _first_audio_logged = False
                        
                        yield event
                    
                    # Check for interruption
                    # 🔥 FIX: Changed from elif to if - messages can have multiple attributes!
                    if hasattr(server_message, 'interrupted'):
                        event = {
                            'type': 'interrupted',
                            'data': None
                        }
                        
                        logger.info("⚠️ [GEMINI_RECV] interrupted")
                        yield event
                    
                    # Check for function calls
                    # 🔥 FIX: Changed from elif to if - messages can have multiple attributes!
                    if hasattr(server_message, 'tool_call'):
                        tool_call = server_message.tool_call
                        
                        # 🔥 FIX 1: Log raw function_call payload (MANDATORY)
                        # Extract all details to understand why function name might be empty
                        function_calls = []
                        if hasattr(tool_call, 'function_calls'):
                            for fc in tool_call.function_calls:
                                fc_data = {
                                    'id': getattr(fc, 'id', 'NO_ID'),
                                    'name': getattr(fc, 'name', 'NO_NAME'),
                                    'args': getattr(fc, 'args', {})
                                }
                                function_calls.append(fc_data)
                                # 🔥 MANDATORY: Log full function_call details
                                logger.info(f"🔧 [GEMINI_RECV] function_call.name={fc_data['name']} call_id={fc_data['id']} args={fc_data['args']}")
                                _orig_print(f"🔧 [GEMINI_RECV] function_call.name={fc_data['name']} call_id={fc_data['id'][:20]}... args={str(fc_data['args'])[:100]}", flush=True)
                        else:
                            # 🔥 FIX: Downgrade to debug to prevent spam for empty tool_calls
                            # This can happen when Gemini sends empty text (greeting trigger)
                            logger.debug(f"[GEMINI_RECV] tool_call has no function_calls attribute (likely empty greeting trigger)")
                        
                        if not IS_PROD or REALTIME_VERBOSE:
                            logger.info(f"[GEMINI_LIVE] Function call received: {function_calls}")
                        
                        event = {
                            'type': 'function_call',
                            'data': tool_call,
                            'function_calls': function_calls  # Include parsed data for easier handling
                        }
                        
                        yield event
                
                except Exception as parse_error:
                    logger.error(f"❌ [GEMINI_RECV] Error parsing message: {parse_error}")
                    logger.exception(f"[GEMINI_THREAD_CRASH] Exception in recv_events parse", exc_info=True)
                    continue
        
        except Exception as e:
            logger.error(f"❌ [GEMINI_RECV] Error in receive loop: {e}")
            logger.exception(f"[GEMINI_THREAD_CRASH] Exception in recv_events loop", exc_info=True)
            raise
    
    async def send_tool_response(self, function_responses: list):
        """
        Send tool/function response back to Gemini Live API
        
        Args:
            function_responses: List of FunctionResponse objects
                Each response should have: id, name, response (dict with result)
        
        Example:
            function_response = types.FunctionResponse(
                id=fc.id,
                name=fc.name,
                response={"result": "success", "data": {...}}
            )
            await client.send_tool_response([function_response])
        """
        if not self._connected or not self.session:
            raise RuntimeError("Not connected. Call connect() first.")
        
        try:
            logger.info(f"🔧 [GEMINI_SEND] Sending {len(function_responses)} tool response(s)")
            await self.session.send_tool_response(function_responses=function_responses)
            logger.debug(f"[GEMINI_LIVE] Tool responses sent successfully")
        except Exception as e:
            logger.error(f"❌ [GEMINI_SEND] Failed to send tool response: {e}")
            logger.exception(f"[GEMINI_THREAD_CRASH] Exception in send_tool_response", exc_info=True)
            raise
    
    async def cancel_response(self, response_id: Optional[str] = None):
        """
        Cancel current response (for barge-in support)
        
        Args:
            response_id: Response ID to cancel (ignored for Gemini, cancels current)
        """
        if not self._connected or not self.session:
            logger.warning("[GEMINI_LIVE] Cannot cancel - not connected")
            return
        
        try:
            # Gemini Live API: Send empty text to interrupt current response
            # Using send_realtime_input with empty text for barge-in
            await self.session.send_realtime_input(text="")
            logger.info("[GEMINI_LIVE] Response cancelled (barge-in)")
        except Exception as e:
            logger.error(f"[GEMINI_LIVE] Failed to cancel response: {e}")
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._connected and self.session is not None
