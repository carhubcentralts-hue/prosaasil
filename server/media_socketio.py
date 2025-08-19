"""
SocketIO Media Streaming Handler
Real-time Hebrew AI conversation processing via SocketIO
"""
import json
import base64
import logging
import time
from typing import Optional
from flask import current_app
from flask_socketio import emit
from server.logging_setup import set_request_context
from server.stream_state import stream_registry

log = logging.getLogger(__name__)

def handle_twilio_media(data):
    """Handle Twilio Media Stream via SocketIO"""
    try:
        if isinstance(data, str):
            message_data = json.loads(data)
        else:
            message_data = data
            
        event = message_data.get('event')
        
        print(f"🔥 SocketIO Media message: {event}", flush=True)
        
        if event == 'connected':
            log.info("SocketIO Media stream connected")
            print("✅ SocketIO Media Streams connected successfully", flush=True)
            
        elif event == 'start':
            # Extract parameters
            call_sid = message_data.get('start', {}).get('callSid')
            stream_sid = message_data.get('start', {}).get('streamSid')
            custom_params = message_data.get('start', {}).get('customParameters', {})
            business_id = custom_params.get('business_id', '1')
            
            # Set logging context
            set_request_context(call_sid, business_id)
            
            log.info("SOCKETIO_START", extra={
                "call_sid": call_sid,
                "stream_sid": stream_sid,
                "business_id": business_id,
                "media_format": message_data.get('start', {}).get('mediaFormat')
            })
            
            # Mark stream as started
            if call_sid:
                stream_registry.mark_start(call_sid)
                stream_registry.touch_media(call_sid)  # Mark media activity
                print(f"✅ SocketIO stream registry marked start for {call_sid}", flush=True)
            
            print(f"📡 SocketIO START: call={call_sid}, streamSid={stream_sid}", flush=True)
            
            # Send welcome message back to caller
            _send_hebrew_welcome(stream_sid)
            
        elif event == 'media':
            # Handle media (audio) data
            # Mark media activity - simplified
            print("🎤 Media activity detected", flush=True)
                
            media_data = message_data.get('media', {})
            payload = media_data.get('payload')
            
            if payload:
                # Process audio with Whisper
                _process_audio_chunk(payload)
                
        elif event == 'stop':
            call_sid = message_data.get('stop', {}).get('callSid')
            print(f"📞 SocketIO Media stream stopped for {call_sid}", flush=True)
            
            if call_sid:
                print(f"📞 SocketIO Media ended for {call_sid}", flush=True)
                
    except Exception as e:
        log.error("SocketIO Media handler error: %s", e)
        print(f"❌ SocketIO Media error: {e}", flush=True)

def _send_hebrew_welcome(stream_sid):
    """Send Hebrew welcome message to caller via TTS"""
    try:
        welcome_text = "שלום! אני עוזר וירטואלי של שי דירות ומשרדים. איך אני יכול לעזור לך היום?"
        
        # Generate TTS - simplified for now
        print(f"🎵 Would generate Hebrew TTS: {welcome_text}", flush=True)
        # TODO: Implement TTS generation
        audio_data = None
        
        if audio_data:
            # Send audio back to caller
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            media_message = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {
                    "payload": audio_b64
                }
            }
            
            emit('message', json.dumps(media_message), namespace='/twilio-media')
            print("🎵 Hebrew welcome sent via SocketIO", flush=True)
            
    except Exception as e:
        print(f"❌ Hebrew welcome TTS error: {e}", flush=True)

def _process_audio_chunk(payload):
    """Process audio chunk with Whisper transcription"""
    try:
        # Decode audio
        audio_data = base64.b64decode(payload)
        
        # Skip processing very small chunks
        if len(audio_data) < 1000:
            return
            
        # TODO: Implement Whisper transcription
        # For now, just log that we received audio
        print(f"🎤 Audio chunk received: {len(audio_data)} bytes", flush=True)
        
        # TODO: Send to OpenAI Whisper
        # TODO: Process with GPT-4o
        # TODO: Generate Hebrew TTS response
        # TODO: Send back to caller
        
    except Exception as e:
        print(f"❌ Audio processing error: {e}", flush=True)