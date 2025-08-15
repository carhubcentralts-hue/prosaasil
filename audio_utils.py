"""
Audio utilities for Media Streams processing
עזרי שמע לעיבוד Media Streams
"""
import base64
import numpy as np
import audioop
import logging

log = logging.getLogger("audio_utils")

def b64_to_mulaw(b64_string: str) -> np.ndarray:
    """Convert base64 encoded audio to μ-law bytes"""
    try:
        audio_bytes = base64.b64decode(b64_string)
        return np.frombuffer(audio_bytes, dtype=np.uint8)
    except Exception as e:
        log.error(f"Failed to decode b64 audio: {e}")
        return np.array([], dtype=np.uint8)

def mulaw8k_to_pcm16k(mulaw_data: np.ndarray) -> np.ndarray:
    """Convert μ-law 8kHz to PCM 16kHz float32 [-1,1]"""
    try:
        if len(mulaw_data) == 0:
            return np.array([], dtype=np.float32)
        
        # Convert μ-law to linear PCM (16-bit)
        mulaw_bytes = mulaw_data.tobytes()
        pcm_bytes = audioop.ulaw2lin(mulaw_bytes, 2)  # 2 bytes per sample (16-bit)
        pcm16_8k = np.frombuffer(pcm_bytes, dtype=np.int16)
        
        # Upsample from 8kHz to 16kHz (simple repeat)
        pcm16_16k = np.repeat(pcm16_8k, 2)
        
        # Convert to float32 [-1, 1]
        pcm_float = pcm16_16k.astype(np.float32) / 32768.0
        
        return pcm_float
        
    except Exception as e:
        log.error(f"Failed to convert μ-law to PCM: {e}")
        return np.array([], dtype=np.float32)

def pcm16k_float_to_mulaw8k_frames(audio: np.ndarray, frame_duration_ms: int = 20) -> list:
    """Convert PCM 16kHz float32 to μ-law 8kHz frames"""
    try:
        if len(audio) == 0:
            return []
        
        # Downsample from 16kHz to 8kHz (simple decimation)
        audio_8k = audio[::2]  # Take every other sample
        
        # Convert float32 [-1,1] to int16
        audio_int16 = (audio_8k * 32767).astype(np.int16)
        
        # Convert to μ-law
        pcm_bytes = audio_int16.tobytes()
        mulaw_bytes = audioop.lin2ulaw(pcm_bytes, 2)
        
        # Split into frames (20ms = 160 samples at 8kHz)
        samples_per_frame = int(8000 * frame_duration_ms / 1000)
        frames = []
        
        for i in range(0, len(mulaw_bytes), samples_per_frame):
            frame = mulaw_bytes[i:i + samples_per_frame]
            if len(frame) == samples_per_frame:  # Only complete frames
                b64_frame = base64.b64encode(frame).decode('utf-8')
                frames.append(b64_frame)
        
        return frames
        
    except Exception as e:
        log.error(f"Failed to convert PCM to μ-law frames: {e}")
        return []