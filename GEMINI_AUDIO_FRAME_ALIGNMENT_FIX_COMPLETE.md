# Gemini Audio Frame Alignment Fix - Complete Implementation

## Problem Overview

The system was experiencing a critical audio streaming failure with the error:

```
[GEMINI_NORMALIZE] Audio conversion failed: not a whole number of frames
```

### Root Cause

Gemini Live API sends audio in PCM16 format (24kHz, 16-bit, mono), but the chunks arrive **unaligned** to frame boundaries. For example, a chunk might be 47 bytes, which equals 23.5 frames (since each frame is 2 bytes for PCM16 mono). When the code tried to process this directly with `audioop.ratecv()`, it failed because the function requires data that's a whole number of frames.

The error log showed:
- `audio_chunk (FIRST): 47 bytes` - an odd number that cannot represent complete PCM16 frames
- This caused the conversion pipeline to crash
- No audio reached Twilio → silence on the call

## Solution Architecture

### 1. Frame Alignment Buffer

Added a buffer to accumulate audio chunks until complete frames are available:

```python
# In MediaStreamHandler.__init__()
self._gemini_audio_buffer = bytearray()  # Accumulates unaligned chunks
self._gemini_audio_frame_size = 2  # PCM16 mono: 2 bytes per sample
```

### 2. Frame Boundary Processing

Updated `_normalize_gemini_event()` to process only complete frames:

```python
# Add incoming chunk to buffer
self._gemini_audio_buffer.extend(audio_bytes)

# Calculate how many complete frames we have
buffer_len = len(self._gemini_audio_buffer)
usable_len = (buffer_len // self._gemini_audio_frame_size) * self._gemini_audio_frame_size

# Extract complete frames, buffer remainder
audio_to_convert = bytes(self._gemini_audio_buffer[:usable_len])
self._gemini_audio_buffer = self._gemini_audio_buffer[usable_len:]
```

### 3. Error Handling

Added resilient error handling to prevent crashes:

```python
try:
    # Process audio...
except Exception as e:
    logger.error(f"[GEMINI_NORMALIZE] Audio conversion failed (chunk #{self._gemini_audio_chunks_received}): {e}")
    # Clear buffer on error to prevent corruption
    self._gemini_audio_buffer.clear()
    return None
```

## Example Flow

### Without Fix (BROKEN)
```
Chunk 1: 47 bytes → audioop.ratecv() → ERROR: not a whole number of frames
No audio sent to Twilio → SILENCE
```

### With Fix (WORKING)
```
Chunk 1: 47 bytes
  → Buffer: 0 + 47 = 47 bytes
  → Usable: 46 bytes (23 frames)
  → Convert 46 bytes → Success
  → Buffer remainder: 1 byte

Chunk 2: 47 bytes
  → Buffer: 1 + 47 = 48 bytes
  → Usable: 48 bytes (24 frames)
  → Convert 48 bytes → Success
  → Buffer remainder: 0 bytes
  
Audio continuously flows to Twilio → WORKING CALL
```

## Additional Improvements

### 1. Validation
- Check if data is actually bytes (not string/base64)
- Skip empty chunks gracefully
- Log first chunk details for debugging (mime_type, hex dump)

### 2. State Management
- Added cleanup in `close_session()` to prevent buffer leakage between calls
- Reset first-chunk logging flag for proper debugging of subsequent calls

### 3. Reduced Logging Spam
- Downgraded empty `tool_call` warnings to debug level
- These occur when Gemini sends greeting triggers and aren't actual errors

## Testing

### Unit Tests (11 tests, all passing)
1. ✅ Buffer initialization
2. ✅ Unaligned chunk buffering (47 bytes)
3. ✅ Multiple unaligned chunks
4. ✅ Empty chunk handling
5. ✅ Non-bytes data rejection
6. ✅ Error recovery clears buffer
7. ✅ Single byte buffering
8. ✅ Large aligned chunks
9. ✅ Chunk counter
10. ✅ Three unaligned chunks sequence
11. ✅ Aligned then unaligned chunks

### Validation Script
Demonstrates the fix for the exact 47-byte problem:
```bash
python validate_gemini_audio_fix.py
```

Output:
```
✅ The 'not a whole number of frames' error is FIXED
✅ Unaligned chunks (like 47 bytes) are handled correctly
✅ Buffer accumulates partial frames across chunks
✅ Empty chunks are skipped gracefully
✅ Invalid data is rejected without crashing
✅ Audio flows correctly to Twilio after conversion
```

## Security

✅ CodeQL security scan: No vulnerabilities found

## Audio Pipeline

The complete audio flow with the fix:

```
Gemini Live API (PCM16 24kHz mono)
  ↓
[Receive unaligned chunks]
  ↓
[Frame Alignment Buffer] ← **NEW FIX**
  ↓
[Process complete frames only]
  ↓
audioop.ratecv(24kHz → 8kHz)
  ↓
audioop.lin2ulaw(PCM16 → μ-law)
  ↓
base64.b64encode()
  ↓
Twilio Media Streams (μ-law 8kHz)
```

## Files Changed

1. **server/media_ws_ai.py**
   - Added frame alignment buffer in `__init__`
   - Updated `_normalize_gemini_event` with buffering logic
   - Added state cleanup in `close_session`
   - Fixed first-chunk logging order

2. **server/services/gemini_realtime_client.py**
   - Downgraded empty tool_call warning to debug

3. **test_gemini_audio_frame_alignment.py** (NEW)
   - Comprehensive unit tests for frame alignment

4. **validate_gemini_audio_fix.py** (NEW)
   - Validation script demonstrating the fix

## Deployment Notes

- ✅ No breaking changes
- ✅ Backward compatible
- ✅ No configuration changes needed
- ✅ Automatic for all Gemini Live API calls

## Monitoring

After deployment, verify:
1. No more `[GEMINI_NORMALIZE] Audio conversion failed` errors in logs
2. Successful audio output from Gemini to Twilio
3. First chunk logs show mime_type and byte details for debugging

## Related Issues

This fix addresses the Hebrew-language issue description:
- "not a whole number of frames" error is eliminated
- Gemini's unaligned chunks (47 bytes example) are handled
- Proper 24kHz→8kHz resampling + μ-law encoding
- No crashes on single bad chunk
- Buffer alignment prevents frame boundary errors
