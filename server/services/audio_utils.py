# -*- coding: utf-8 -*-
"""
⚡ BUILD 117 - Audio Utilities for Greeting Cache
Functions for converting TTS audio to μ-law 20ms frames for Twilio
"""
import audioop
import base64
from typing import List

# Constants
SAMPLE_RATE = 8000   # 8kHz for telephony
BYTES_PER_FR = 160   # 20ms μ-law frame = 160 bytes at 8kHz


def pcm16_to_mulaw(pcm16_bytes: bytes) -> bytes:
    """
    Convert PCM16 (little-endian) audio to μ-law 8-bit.
    
    Args:
        pcm16_bytes: Raw PCM16 audio data (16-bit signed, little-endian)
        
    Returns:
        μ-law encoded audio bytes
    """
    return audioop.lin2ulaw(pcm16_bytes, 2)  # 2 = 16-bit samples


def resample_to_8khz(pcm16_bytes: bytes, source_rate: int) -> bytes:
    """
    Resample PCM16 audio from source rate to 8kHz.
    
    Args:
        pcm16_bytes: Raw PCM16 audio data
        source_rate: Source sample rate (e.g., 22050, 24000)
        
    Returns:
        Resampled PCM16 audio at 8kHz
    """
    if source_rate == SAMPLE_RATE:
        return pcm16_bytes
    
    # audioop.ratecv(fragment, width, nchannels, inrate, outrate, state)
    resampled, _ = audioop.ratecv(
        pcm16_bytes,
        2,  # 16-bit = 2 bytes per sample
        1,  # mono
        source_rate,
        SAMPLE_RATE,
        None  # no state needed for one-shot conversion
    )
    return resampled


def split_mulaw_to_20ms_frames(mulaw_bytes: bytes) -> List[str]:
    """
    Split μ-law audio into 20ms frames and encode as base64.
    
    Each frame is 160 bytes (20ms at 8kHz).
    Incomplete frames at the end are discarded.
    
    Args:
        mulaw_bytes: μ-law encoded audio data
        
    Returns:
        List of base64-encoded 20ms audio frames
    """
    frames_b64 = []
    
    for i in range(0, len(mulaw_bytes), BYTES_PER_FR):
        chunk = mulaw_bytes[i : i + BYTES_PER_FR]
        
        # Only include complete frames
        if len(chunk) < BYTES_PER_FR:
            break
        
        # Encode to base64 for transmission
        frames_b64.append(base64.b64encode(chunk).decode('ascii'))
    
    return frames_b64


def pcm16_to_frames(pcm16_bytes: bytes, source_rate: int = 8000) -> List[str]:
    """
    Complete pipeline: PCM16 → resample → μ-law → 20ms frames.
    
    Args:
        pcm16_bytes: Raw PCM16 audio data
        source_rate: Source sample rate (default 8000)
        
    Returns:
        List of base64-encoded 20ms μ-law frames ready for Twilio
    """
    # Step 1: Resample to 8kHz if needed
    if source_rate != SAMPLE_RATE:
        pcm16_8k = resample_to_8khz(pcm16_bytes, source_rate)
    else:
        pcm16_8k = pcm16_bytes
    
    # Step 2: Convert to μ-law
    mulaw = pcm16_to_mulaw(pcm16_8k)
    
    # Step 3: Split into 20ms frames and base64 encode
    frames = split_mulaw_to_20ms_frames(mulaw)
    
    return frames
