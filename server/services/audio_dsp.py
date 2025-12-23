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
- PER-CALL state - filter state is isolated per call instance
"""
import numpy as np
import audioop
import math
import logging
from typing import Optional

# Get logger for this module
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# DSP Parameters - Tuned for telephony (8kHz, 20ms frames)
# ═══════════════════════════════════════════════════════════════════════════════
SAMPLE_RATE = 8000  # Telephony standard
HIGHPASS_CUTOFF_HZ = 120.0  # Remove low-frequency noise/rumble
LIMITER_THRESHOLD = 28000  # Soft limiter threshold (leaves headroom)
LIMITER_RATIO = 4.0  # Gentle compression ratio (not a brick wall)

# RMS logging - log every N frames to avoid overhead
RMS_LOG_INTERVAL = 100  # Log RMS stats every 100 frames (~2 seconds)

# Filter coefficient (computed once)
_FILTER_ALPHA = math.exp(-2.0 * math.pi * HIGHPASS_CUTOFF_HZ / SAMPLE_RATE)


class AudioDSPProcessor:
    """
    Per-call DSP processor with isolated filter state
    
    Each call should create its own instance to avoid state leaking between calls.
    This ensures filter state (previous input/output) doesn't carry over from
    previous calls.
    
    Usage:
        processor = AudioDSPProcessor()
        processed_audio = processor.process(mulaw_bytes)
    """
    
    def __init__(self):
        """Initialize DSP processor with clean state"""
        # High-pass filter state (per-instance, not global!)
        self._filter_prev_input = 0.0
        self._filter_prev_output = 0.0
        
        # RMS logging counter
        self._rms_frame_counter = 0
    
    def _highpass_filter_sample(self, sample: float) -> float:
        """
        Apply 1st order high-pass filter to single sample
        
        This is a simple recursive filter that removes DC offset and low frequencies.
        State is maintained across calls for frame continuity WITHIN a call.
        
        Args:
            sample: Input sample (float)
        
        Returns:
            Filtered sample (float)
        """
        # IIR difference equation: y[n] = (x[n] - x[n-1]) - alpha * y[n-1]
        output = sample - self._filter_prev_input - _FILTER_ALPHA * self._filter_prev_output
        
        # Update state
        self._filter_prev_input = sample
        self._filter_prev_output = output
        
        return output
    
    def _calculate_rms(self, pcm16_data: bytes) -> float:
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
    
    def process(self, mulaw_bytes: bytes) -> bytes:
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
        if not mulaw_bytes:
            return mulaw_bytes
        
        try:
            # ═══════════════════════════════════════════════════════════════════════
            # STEP 1: μ-law → PCM16 (decode)
            # ═══════════════════════════════════════════════════════════════════════
            pcm16_data = audioop.ulaw2lin(mulaw_bytes, 2)  # 2 = 16-bit samples
            
            # Calculate RMS before processing (for logging)
            rms_before = None
            self._rms_frame_counter += 1
            if self._rms_frame_counter >= RMS_LOG_INTERVAL:
                rms_before = self._calculate_rms(pcm16_data)
            
            # ═══════════════════════════════════════════════════════════════════════
            # STEP 2: High-pass filter + Soft limiter
            # ═══════════════════════════════════════════════════════════════════════
            # Convert to numpy for efficient processing
            samples = np.frombuffer(pcm16_data, dtype=np.int16).astype(np.float64)
            
            # Apply high-pass filter (sample-by-sample for state continuity)
            # Note: Must use loop to maintain filter state across samples
            filtered_samples = np.empty_like(samples)
            for i, sample in enumerate(samples):
                filtered_samples[i] = self._highpass_filter_sample(sample)
            
            # Apply soft limiter (vectorized for performance)
            abs_samples = np.abs(filtered_samples)
            
            # Vectorized soft limiter logic
            # No limiting needed if below threshold
            limited_samples = filtered_samples.copy()
            
            # Apply limiting only to samples above threshold
            needs_limiting = abs_samples > LIMITER_THRESHOLD
            if np.any(needs_limiting):
                excess = abs_samples[needs_limiting] - LIMITER_THRESHOLD
                compressed_excess = excess / LIMITER_RATIO
                limited_abs = LIMITER_THRESHOLD + compressed_excess
                # Preserve sign
                limited_samples[needs_limiting] = np.sign(filtered_samples[needs_limiting]) * limited_abs
            
            # Convert back to int16
            processed_samples = np.clip(limited_samples, -32768, 32767).astype(np.int16)
            pcm16_processed = processed_samples.tobytes()
            
            # ═══════════════════════════════════════════════════════════════════════
            # STEP 3: PCM16 → μ-law (encode)
            # ═══════════════════════════════════════════════════════════════════════
            mulaw_processed = audioop.lin2ulaw(pcm16_processed, 2)
            
            # ═══════════════════════════════════════════════════════════════════════
            # LOGGING: RMS before/after (DEBUG level to avoid production spam)
            # ═══════════════════════════════════════════════════════════════════════
            if rms_before is not None:
                rms_after = self._calculate_rms(pcm16_processed)
                logger.debug(f"[DSP] RMS: before={rms_before:.1f}, after={rms_after:.1f}, delta={rms_after-rms_before:.1f}")
                self._rms_frame_counter = 0  # Reset counter
            
            return mulaw_processed
            
        except Exception as e:
            # Failsafe: return original audio if DSP fails
            logger.error(f"[DSP] ERROR: {e} - returning original audio")
            return mulaw_bytes


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy API - For backward compatibility with existing code
# ═══════════════════════════════════════════════════════════════════════════════
# DEPRECATED: Global state version - kept for backward compatibility
# New code should use AudioDSPProcessor class instead
_global_processor = AudioDSPProcessor()


def dsp_mulaw_8k(mulaw_bytes: bytes) -> bytes:
    """
    DEPRECATED: Use AudioDSPProcessor.process() instead
    
    This function uses a global processor instance, which means filter state
    can leak between calls. For proper per-call isolation, create an
    AudioDSPProcessor instance per call.
    
    Args:
        mulaw_bytes: Input audio in μ-law format
    
    Returns:
        Processed audio in μ-law format
    """
    return _global_processor.process(mulaw_bytes)


def reset_filter_state():
    """
    DEPRECATED: Use AudioDSPProcessor() constructor instead
    
    This function resets the global processor state. For proper per-call
    isolation, create a new AudioDSPProcessor instance per call instead.
    """
    global _global_processor
    _global_processor = AudioDSPProcessor()

