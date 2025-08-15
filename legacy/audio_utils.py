# audio_utils.py
import base64
import audioop
import numpy as np
import librosa

def b64_to_mulaw(b64): 
    return base64.b64decode(b64)

def mulaw8k_to_pcm16k(mulaw_bytes: bytes) -> np.ndarray:
    # μ-law (8k) -> PCM16 8k -> ריסמפל ל-16k -> float32 [-1,1]
    pcm8 = audioop.ulaw2lin(mulaw_bytes, 2)           # bytes PCM16 @8k
    pcm8_np = np.frombuffer(pcm8, dtype=np.int16).astype(np.float32) / 32768.0
    pcm16 = librosa.resample(pcm8_np, orig_sr=8000, target_sr=16000)
    return pcm16

def pcm16k_float_to_mulaw8k_frames(pcm16: np.ndarray, frame_ms: int = 20):
    """מקבל float32 @16k, מחזיר generator של פריימי μ-law@8k בבסיס־64 באורך 20ms כל אחד"""
    # חזרה ל-int16@16k
    int16_16k = (np.clip(pcm16, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
    # downsample ל-8k
    pcm16_8k = librosa.resample(np.frombuffer(int16_16k, dtype=np.int16).astype(np.float32)/32768.0, orig_sr=16000, target_sr=8000)
    int16_8k = (np.clip(pcm16_8k, -1.0, 1.0)*32767).astype(np.int16).tobytes()
    # המרה ל-μ-law
    mulaw = audioop.lin2ulaw(int16_8k, 2)  # bytes @8k
    # חיתוך ל-20ms (160 דגימות @8k = 160 bytes μ-law)
    step = 160
    for i in range(0, len(mulaw), step):
        yield base64.b64encode(mulaw[i:i+step]).decode()