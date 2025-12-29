"""
Audio Codec Conversion - g711 ulaw <-> PCM16
Efficient, non-blocking conversion between Asterisk and OpenAI formats
"""
import audioop
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Constants for audio conversion
SAMPLE_RATE = 8000  # 8kHz for g711
FRAME_DURATION_MS = 20  # 20ms frames
SAMPLES_PER_FRAME = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 160 samples
BYTES_PER_FRAME_ULAW = SAMPLES_PER_FRAME  # 1 byte per sample for ulaw
BYTES_PER_FRAME_PCM16 = SAMPLES_PER_FRAME * 2  # 2 bytes per sample for PCM16


class AudioCodec:
    """
    Audio codec converter for g711 ulaw and PCM16.
    
    Provides efficient, non-blocking conversion between:
    - g711 ulaw (8-bit, 8kHz) - used by Asterisk
    - PCM16 (16-bit, 24kHz) - used by OpenAI Realtime API
    
    Frame size: 20ms (160 samples at 8kHz, 480 samples at 24kHz)
    """
    
    @staticmethod
    def ulaw_to_pcm16(ulaw_data: bytes) -> Optional[bytes]:
        """
        Convert g711 ulaw to PCM16.
        
        Args:
            ulaw_data: g711 ulaw audio data (8-bit, 8kHz)
            
        Returns:
            PCM16 audio data (16-bit, 8kHz) or None if conversion fails
        """
        try:
            # Use audioop for efficient conversion
            # ulaw2lin converts ulaw to linear PCM
            pcm_data = audioop.ulaw2lin(ulaw_data, 2)  # 2 = 16-bit samples
            return pcm_data
            
        except Exception as e:
            logger.error(f"[CODEC] Failed to convert ulaw to PCM16: {e}")
            return None
    
    @staticmethod
    def pcm16_to_ulaw(pcm_data: bytes) -> Optional[bytes]:
        """
        Convert PCM16 to g711 ulaw.
        
        Args:
            pcm_data: PCM16 audio data (16-bit, 8kHz or 24kHz)
            
        Returns:
            g711 ulaw audio data (8-bit, 8kHz) or None if conversion fails
        """
        try:
            # Use audioop for efficient conversion
            # lin2ulaw converts linear PCM to ulaw
            ulaw_data = audioop.lin2ulaw(pcm_data, 2)  # 2 = 16-bit samples
            return ulaw_data
            
        except Exception as e:
            logger.error(f"[CODEC] Failed to convert PCM16 to ulaw: {e}")
            return None
    
    @staticmethod
    def resample_pcm16(pcm_data: bytes, from_rate: int, to_rate: int) -> Optional[bytes]:
        """
        Resample PCM16 audio between different sample rates.
        
        Args:
            pcm_data: PCM16 audio data
            from_rate: Source sample rate (e.g., 8000)
            to_rate: Target sample rate (e.g., 24000)
            
        Returns:
            Resampled PCM16 audio data or None if conversion fails
        """
        try:
            # Use audioop.ratecv for resampling
            # ratecv(fragment, width, nchannels, inrate, outrate, state)
            resampled, _ = audioop.ratecv(
                pcm_data,
                2,  # 16-bit samples
                1,  # mono
                from_rate,
                to_rate,
                None  # no state needed for single conversion
            )
            return resampled
            
        except Exception as e:
            logger.error(f"[CODEC] Failed to resample {from_rate}Hz to {to_rate}Hz: {e}")
            return None
    
    @staticmethod
    def ulaw_to_pcm24k(ulaw_data: bytes) -> Optional[bytes]:
        """
        Convert g711 ulaw (8kHz) to PCM16 (24kHz) for OpenAI Realtime.
        
        This is the main conversion for incoming audio from Asterisk.
        
        Args:
            ulaw_data: g711 ulaw audio (8-bit, 8kHz)
            
        Returns:
            PCM16 audio (16-bit, 24kHz) or None if conversion fails
        """
        # Step 1: ulaw to PCM16 at 8kHz
        pcm_8k = AudioCodec.ulaw_to_pcm16(ulaw_data)
        if not pcm_8k:
            return None
        
        # Step 2: Resample from 8kHz to 24kHz
        pcm_24k = AudioCodec.resample_pcm16(pcm_8k, 8000, 24000)
        return pcm_24k
    
    @staticmethod
    def pcm24k_to_ulaw(pcm_data: bytes) -> Optional[bytes]:
        """
        Convert PCM16 (24kHz) from OpenAI to g711 ulaw (8kHz) for Asterisk.
        
        This is the main conversion for outgoing audio to Asterisk.
        
        Args:
            pcm_data: PCM16 audio (16-bit, 24kHz)
            
        Returns:
            g711 ulaw audio (8-bit, 8kHz) or None if conversion fails
        """
        # Step 1: Resample from 24kHz to 8kHz
        pcm_8k = AudioCodec.resample_pcm16(pcm_data, 24000, 8000)
        if not pcm_8k:
            return None
        
        # Step 2: PCM16 to ulaw
        ulaw_data = AudioCodec.pcm16_to_ulaw(pcm_8k)
        return ulaw_data
    
    @staticmethod
    def validate_frame_size(data: bytes, expected_size: int, codec: str) -> bool:
        """
        Validate audio frame size.
        
        Args:
            data: Audio data
            expected_size: Expected size in bytes
            codec: Codec name for logging
            
        Returns:
            True if size is valid
        """
        if len(data) != expected_size:
            logger.warning(
                f"[CODEC] Invalid {codec} frame size: "
                f"got {len(data)} bytes, expected {expected_size}"
            )
            return False
        return True
    
    @staticmethod
    def create_silence_frame(codec: str = "ulaw") -> bytes:
        """
        Create a silence frame for the specified codec.
        
        Args:
            codec: Codec type ("ulaw" or "pcm16")
            
        Returns:
            Silence frame bytes
        """
        if codec == "ulaw":
            # Silence in ulaw is 0xFF (127 in linear)
            return bytes([0xFF] * BYTES_PER_FRAME_ULAW)
        elif codec == "pcm16":
            # Silence in PCM16 is 0x0000
            return bytes([0x00] * BYTES_PER_FRAME_PCM16)
        else:
            raise ValueError(f"Unknown codec: {codec}")


class AudioFrameBuffer:
    """
    Buffer for accumulating audio frames to ensure proper 20ms framing.
    
    Handles partial frames and accumulates data until a complete 20ms frame
    is available.
    """
    
    def __init__(self, frame_size: int):
        """
        Initialize frame buffer.
        
        Args:
            frame_size: Expected frame size in bytes
        """
        self.frame_size = frame_size
        self.buffer = bytearray()
        
        logger.debug(f"[FRAME_BUFFER] Initialized: frame_size={frame_size}")
    
    def add_data(self, data: bytes) -> list[bytes]:
        """
        Add data to buffer and return complete frames.
        
        Args:
            data: Audio data to add
            
        Returns:
            List of complete frames (may be empty)
        """
        self.buffer.extend(data)
        
        frames = []
        while len(self.buffer) >= self.frame_size:
            # Extract one complete frame
            frame = bytes(self.buffer[:self.frame_size])
            frames.append(frame)
            
            # Remove from buffer
            self.buffer = self.buffer[self.frame_size:]
        
        return frames
    
    def get_buffered_size(self) -> int:
        """Get current buffer size in bytes."""
        return len(self.buffer)
    
    def clear(self):
        """Clear buffer."""
        self.buffer.clear()
