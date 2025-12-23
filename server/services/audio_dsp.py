"""
Minimal DSP for audio quality improvement - High-pass + Soft limiter

This module provides surgical audio processing to reduce background noise/music
without affecting speech quality. Processing chain:

1. μ-law (8kHz) → PCM16
2. High-pass filter (120Hz, 1st order) - removes low-frequency rumble/hum
3. Soft limiter (gentle, no gate) - prevents clipping, maintains dynamics
4. PCM16 → μ-law (8kHz)

Design principles:
- MINIMAL processing - only what's necessary
- NO aggressive gating - preserves speech naturalness
- NO noise floor detection - keeps it simple
- Fast execution - suitable for real-time telephony (20ms frames)
"""
import numpy as np
import audioop
import math
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# DSP Parameters - Tuned for telephony (8kHz, 20ms frames)
# ═══════════════════════════════════════════════════════════════════════════════
SAMPLE_RATE = 8000  # Telephony standard
HIGHPASS_CUTOFF_HZ = 120.0  # Remove low-frequency noise/rumble
LIMITER_THRESHOLD = 28000  # Soft limiter threshold (leaves headroom)
LIMITER_RATIO = 4.0  # Gentle compression ratio (not a brick wall)

# RMS logging - log every N frames to avoid overhead
RMS_LOG_INTERVAL = 100  # Log RMS stats every 100 frames (~2 seconds)
_rms_frame_counter = 0


# ═══════════════════════════════════════════════════════════════════════════════
# High-pass filter state (persistent across frames for continuity)
# ═══════════════════════════════════════════════════════════════════════════════
# Simple 1st order IIR high-pass filter (Butterworth)
# Transfer function: H(z) = (1 - z^-1) / (1 - alpha * z^-1)
# where alpha = e^(-2π * fc / fs)
_filter_alpha = math.exp(-2.0 * math.pi * HIGHPASS_CUTOFF_HZ / SAMPLE_RATE)
_filter_prev_input = 0.0
_filter_prev_output = 0.0


def _highpass_filter_sample(sample: float) -> float:
    """
    Apply 1st order high-pass filter to single sample
    
    This is a simple recursive filter that removes DC offset and low frequencies.
    State is maintained across calls for frame continuity.
    
    Args:
        sample: Input sample (float)
    
    Returns:
        Filtered sample (float)
    """
    global _filter_prev_input, _filter_prev_output
    
    # IIR difference equation: y[n] = (x[n] - x[n-1]) - alpha * y[n-1]
    output = sample - _filter_prev_input - _filter_alpha * _filter_prev_output
    
    # Update state
    _filter_prev_input = sample
    _filter_prev_output = output
    
    return output


def _soft_limiter(sample: float) -> float:
    """
    Apply soft limiter to prevent clipping while maintaining dynamics
    
    This is a gentle compressor, not a hard clipper. It gradually reduces
    gain as signal approaches threshold, maintaining natural sound.
    
    Args:
        sample: Input sample (float, -32768 to 32767)
    
    Returns:
        Limited sample (float, same range)
    """
    abs_sample = abs(sample)
    
    # No limiting needed if below threshold
    if abs_sample <= LIMITER_THRESHOLD:
        return sample
    
    # Calculate gain reduction using soft knee
    # gain = threshold + (input - threshold) / ratio
    excess = abs_sample - LIMITER_THRESHOLD
    compressed_excess = excess / LIMITER_RATIO
    limited_abs = LIMITER_THRESHOLD + compressed_excess
    
    # Apply to original sample (preserving sign)
    if sample >= 0:
        return limited_abs
    else:
        return -limited_abs


def _calculate_rms(pcm16_data: bytes) -> float:
    """
    Calculate RMS (Root Mean Square) of PCM16 audio
    
    RMS is a measure of average signal power, useful for monitoring
    audio levels before/after DSP processing.
    
    Args:
        pcm16_data: PCM16 audio bytes (16-bit signed, little-endian)
    
    Returns:
        RMS value (0-32768)
    """
    if not pcm16_data or len(pcm16_data) < 2:
        return 0.0
    
    # Convert bytes to numpy array of int16
    samples = np.frombuffer(pcm16_data, dtype=np.int16)
    
    # RMS = sqrt(mean(x^2))
    rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
    
    return float(rms)


def dsp_mulaw_8k(mulaw_bytes: bytes) -> bytes:
    """
    Apply minimal DSP to μ-law audio (8kHz telephony)
    
    Processing chain:
    1. μ-law → PCM16 (decode)
    2. High-pass filter (120Hz) - remove low-frequency noise
    3. Soft limiter - prevent clipping
    4. PCM16 → μ-law (encode)
    
    This function is designed for real-time telephony frames (20ms = 160 bytes).
    Processing time must be < 20ms to avoid audio gaps.
    
    Args:
        mulaw_bytes: Input audio in μ-law format (160 bytes for 20ms frame)
    
    Returns:
        Processed audio in μ-law format (same length as input)
    """
    global _rms_frame_counter
    
    if not mulaw_bytes:
        return mulaw_bytes
    
    try:
        # ═══════════════════════════════════════════════════════════════════════
        # STEP 1: μ-law → PCM16 (decode)
        # ═══════════════════════════════════════════════════════════════════════
        pcm16_data = audioop.ulaw2lin(mulaw_bytes, 2)  # 2 = 16-bit samples
        
        # Calculate RMS before processing (for logging)
        rms_before = None
        _rms_frame_counter += 1
        if _rms_frame_counter >= RMS_LOG_INTERVAL:
            rms_before = _calculate_rms(pcm16_data)
        
        # ═══════════════════════════════════════════════════════════════════════
        # STEP 2: High-pass filter + Soft limiter
        # ═══════════════════════════════════════════════════════════════════════
        # Convert to numpy for efficient processing
        samples = np.frombuffer(pcm16_data, dtype=np.int16).astype(np.float64)
        
        # Apply high-pass filter (sample-by-sample for state continuity)
        filtered_samples = np.array([_highpass_filter_sample(s) for s in samples])
        
        # Apply soft limiter
        limited_samples = np.array([_soft_limiter(s) for s in filtered_samples])
        
        # Convert back to int16
        processed_samples = np.clip(limited_samples, -32768, 32767).astype(np.int16)
        pcm16_processed = processed_samples.tobytes()
        
        # ═══════════════════════════════════════════════════════════════════════
        # STEP 3: PCM16 → μ-law (encode)
        # ═══════════════════════════════════════════════════════════════════════
        mulaw_processed = audioop.lin2ulaw(pcm16_processed, 2)
        
        # ═══════════════════════════════════════════════════════════════════════
        # LOGGING: RMS before/after (every N frames to avoid overhead)
        # ═══════════════════════════════════════════════════════════════════════
        if rms_before is not None:
            rms_after = _calculate_rms(pcm16_processed)
            print(f"[DSP] RMS: before={rms_before:.1f}, after={rms_after:.1f}, delta={rms_after-rms_before:.1f}")
            _rms_frame_counter = 0  # Reset counter
        
        return mulaw_processed
        
    except Exception as e:
        # Failsafe: return original audio if DSP fails
        print(f"[DSP] ERROR: {e} - returning original audio")
        return mulaw_bytes


def reset_filter_state():
    """
    Reset high-pass filter state (call at start of new call)
    
    This ensures filter doesn't carry over artifacts from previous calls.
    Should be called when a new call starts.
    """
    global _filter_prev_input, _filter_prev_output, _rms_frame_counter
    _filter_prev_input = 0.0
    _filter_prev_output = 0.0
    _rms_frame_counter = 0
