# Fix 502 Bad Gateway on Recording Download Endpoint

## Problem
The `/api/calls/<CallSid>/download` endpoint was returning 502 Bad Gateway errors when users tried to play recordings in the outbound calls tab.

## Root Cause
The issue was caused by two main problems:

1. **Nginx Configuration**: The `/api/` location in nginx.conf lacked proper configuration for:
   - Audio streaming (buffering disabled)
   - Range request headers (needed for HTML5 audio elements and iOS/Android players)
   - Adequate timeouts for large file downloads

2. **Backend Error Handling**: The Flask endpoint and recording service lacked comprehensive error handling, which could cause crashes when:
   - Twilio API was unreachable or timed out
   - Recording files were missing or invalid
   - Network errors occurred during download

## Solution

### 1. Nginx Configuration (`docker/nginx.conf`)
Added streaming support to the `/api/` location block:

```nginx
location /api/ {
    # ... existing headers ...
    
    # Disable buffering for audio streaming (required for large files)
    proxy_buffering off;
    proxy_request_buffering off;
    
    # Pass Range headers for iOS/Android audio players (partial content support)
    proxy_set_header Range $http_range;
    proxy_set_header If-Range $http_if_range;
    
    # Increase timeouts for large file downloads (recordings can be several MB)
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    proxy_connect_timeout 75s;
}
```

**Why this fixes the 502**:
- `proxy_buffering off`: Allows nginx to stream large files without buffering them entirely in memory
- Range headers: Required for HTML5 audio elements to seek within recordings
- Extended timeouts: Prevents nginx from giving up before the backend finishes downloading from Twilio

### 2. Backend Error Handling (`server/routes_calls.py`)
Enhanced the download_recording endpoint with:

- Validation of recording_url before attempting download
- Try-except wrapper around get_recording_file_for_call to prevent crashes
- File existence check before serving
- Comprehensive logging for troubleshooting

```python
# Check if recording_url exists before attempting download
if not call.recording_url:
    log.warning(f"Download recording: No recording_url for call_sid={call_sid}")
    return jsonify({"success": False, "error": "Recording URL not available"}), 404

# Wrap in try-except to prevent crashes from Twilio failures
try:
    audio_path = get_recording_file_for_call(call)
except Exception as fetch_error:
    log.error(f"Download recording: Failed to fetch recording for call_sid={call_sid}: {fetch_error}")
    return jsonify({"success": False, "error": "Failed to fetch recording from Twilio"}), 500
```

### 3. Recording Service Resilience (`server/services/recording_service.py`)
Improved error handling in the recording service:

- Try-except blocks around all critical operations
- Better HTTP status code handling (401, 403, 500+)
- Timeout error handling for hanging Twilio requests
- Specific error messages for each failure type

```python
# Handle different HTTP status codes explicitly
if response.status_code == 401:
    log.error(f"[RECORDING_SERVICE] Authentication failed (401) for {call_sid}")
    return None
elif response.status_code == 403:
    log.error(f"[RECORDING_SERVICE] Access forbidden (403) for {call_sid}")
    return None
elif response.status_code >= 500:
    log.warning(f"[RECORDING_SERVICE] Twilio server error ({response.status_code}) for {call_sid}")
```

## Deployment Instructions

1. **Rebuild Docker containers** to apply nginx.conf changes:
   ```bash
   docker compose build
   ```

2. **Restart services**:
   ```bash
   docker compose restart nginx backend
   ```

3. **Verify the fix**:
   - Navigate to the outbound calls tab
   - Click play on a recording
   - Recording should play without 502 errors

4. **Monitor logs** to ensure no errors:
   ```bash
   # Watch nginx logs for 502 errors
   docker compose logs -f nginx | grep 502
   
   # Watch backend logs for recording download attempts
   docker compose logs -f backend | grep "Download recording"
   ```

## Testing

Run the validation script to verify all changes are in place:
```bash
python validate_recording_fix.py
```

Expected output:
```
✅ PASS: nginx.conf
✅ PASS: routes_calls.py
✅ PASS: recording_service.py

✅ All validations passed!
```

## Troubleshooting

If recordings still don't play:

1. **Check nginx logs**:
   ```bash
   docker compose logs nginx -n 200
   ```
   Look for:
   - `connect() failed (111)` - Backend is down
   - `upstream prematurely closed` - Backend crashed
   - `upstream timed out` - Request took too long

2. **Check backend logs**:
   ```bash
   docker compose logs backend -n 300
   ```
   Look for:
   - `Download recording: Failed to fetch recording` - Twilio API issue
   - `RECORDING_SERVICE` messages - Details about download attempts
   - Python tracebacks - Code errors

3. **Test the endpoint directly**:
   ```bash
   # From within the nginx container
   curl -I http://backend:5000/api/calls/CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/download
   
   # From the host
   curl -I http://localhost/api/calls/CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/download
   ```

4. **Common issues**:
   - **Expired recordings**: Recordings older than 7 days return 410 Gone
   - **Missing Twilio credentials**: Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN
   - **Network issues**: Ensure the backend can reach api.twilio.com

## Files Changed

- `docker/nginx.conf` - Added audio streaming support
- `server/routes_calls.py` - Enhanced error handling
- `server/services/recording_service.py` - Improved resilience

## Related Documentation

- [Twilio Recording API](https://www.twilio.com/docs/voice/api/recording)
- [Nginx Proxy Configuration](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- [HTML5 Audio Element](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/audio)
