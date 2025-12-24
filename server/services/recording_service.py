"""
Recording Service - שירות מאוחד להורדה ושמירה של הקלטות
משמש גם ל-UI וגם ל-offline worker - single source of truth
"""
import os
import logging
import requests
import time
import fcntl
from typing import Optional
from server.models_sql import CallLog
from flask import current_app, has_app_context

log = logging.getLogger(__name__)

# File-based lock configuration
LOCK_TIMEOUT_SECONDS = 45  # Maximum time to wait for lock acquisition
LOCK_POLL_INTERVAL = 0.5   # Check lock availability every 0.5 seconds

def _get_recordings_dir() -> str:
    """
    ✅ מחזיר נתיב מוחלט לתיקיית הקלטות
    תומך בהרצה עם ובלי Flask context
    """
    if has_app_context():
        # Inside Flask app - use root_path (/app/server)
        base_dir = current_app.root_path
    else:
        # Outside Flask (e.g., worker) - use file location
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    recordings_dir = os.path.join(base_dir, "recordings")
    return recordings_dir

def get_recording_file_for_call(call_log: CallLog) -> Optional[str]:
    """
    ✅ SOURCE OF TRUTH: מחזיר path לקובץ הקלטה עבור שיחה
    
    Logic:
    1. אם כבר קיים קובץ מקומי → החזר את הנתיב
    2. אחרת → הורד מטוויליו (בדיוק כמו ה-UI), שמור ב-/app/server/recordings/<call_sid>.mp3
    3. החזר את הנתיב או None אם נכשל
    
    Args:
        call_log: CallLog instance with recording_url
        
    Returns:
        str: Absolute path to local recording file, or None if failed
    """
    # 🔥 FIX 502: Add validation and error handling to prevent crashes
    if not call_log or not call_log.call_sid:
        log.error("[RECORDING_SERVICE] Invalid call_log provided")
        return None
    
    call_sid = call_log.call_sid
    
    # 1. Check if we already have the file locally
    try:
        recordings_dir = _get_recordings_dir()
        os.makedirs(recordings_dir, exist_ok=True)
    except Exception as e:
        log.error(f"[RECORDING_SERVICE] Failed to create recordings directory: {e}")
        return None
    
    # 🔥 FIX: Try both call_sid and parent_call_sid (for outbound child legs)
    # Canonical path: always {call_sid}.mp3, but try parent if child doesn't have recording
    sids_to_try = [call_sid]
    if call_log.parent_call_sid:
        sids_to_try.append(call_log.parent_call_sid)
        log.debug(f"[RECORDING_SERVICE] Will also check parent_call_sid={call_log.parent_call_sid}")
    
    # Check for existing local file (try call_sid first, then parent_call_sid)
    for try_sid in sids_to_try:
        local_path = os.path.join(recordings_dir, f"{try_sid}.mp3")
        
        if os.path.exists(local_path):
            try:
                file_size = os.path.getsize(local_path)
                if file_size > 1000:  # Valid file (>1KB)
                    log.info(f"[RECORDING_SERVICE] ✅ Cache HIT - using existing local file: {local_path} ({file_size} bytes)")
                    return local_path
                else:
                    log.warning(f"[RECORDING_SERVICE] Local file too small ({file_size} bytes), will re-download")
                    os.remove(local_path)
            except Exception as e:
                log.warning(f"[RECORDING_SERVICE] Error checking local file: {e}")
    
    # If we get here, no valid local file exists - need to download
    # Use the primary call_sid for download path
    local_path = os.path.join(recordings_dir, f"{call_sid}.mp3")
    
    # 2. Download from Twilio using call_log.recording_url
    if not call_log.recording_url:
        log.error(f"[RECORDING_SERVICE] No recording_url for call {call_sid}")
        return None
    
    # 🔥 FIX: Use file-based lock to prevent concurrent downloads across multiple workers/pods
    # File locks work across processes and containers sharing the same volume
    lock_file_path = os.path.join(recordings_dir, f".{call_sid}.lock")
    lock_file = None
    
    try:
        # Open lock file (use 'a' mode to avoid truncation race condition)
        lock_file = open(lock_file_path, 'a')
        
        # Try to acquire exclusive lock with timeout
        # LOCK_EX = exclusive lock, LOCK_NB = non-blocking
        attempts = int(LOCK_TIMEOUT_SECONDS / LOCK_POLL_INTERVAL)
        
        lock_acquired = False
        for attempt in range(attempts):
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_acquired = True
                break
            except IOError:
                # Lock is held by another process, wait and retry
                if attempt == 0:
                    log.info(f"[RECORDING_SERVICE] Waiting for lock on {call_sid} (another worker downloading)...")
                time.sleep(LOCK_POLL_INTERVAL)
        
        if not lock_acquired:
            log.warning(f"[RECORDING_SERVICE] Could not acquire file lock for {call_sid} after {LOCK_TIMEOUT_SECONDS}s")
            # Check if file was created by other process while we waited
            for retry in range(3):
                time.sleep(3)
                if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
                    log.info(f"[RECORDING_SERVICE] ✅ File became available while waiting: {local_path}")
                    return local_path
            log.error(f"[RECORDING_SERVICE] Timeout waiting for {call_sid} to be downloaded")
            return None
        
        # Double-check file doesn't exist (another process may have created it before we got lock)
        if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
            log.info(f"[RECORDING_SERVICE] ✅ File already exists (created by another process): {local_path}")
            return local_path
        
        log.warning(f"[RECORDING_SERVICE] ⚠️  Cache miss - downloading from Twilio for {call_sid} (this may take time and cause 502 if slow)")
        download_start = time.time()
        
        # Get Twilio credentials
        try:
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            
            if not account_sid or not auth_token:
                log.error("[RECORDING_SERVICE] Missing Twilio credentials")
                return None
        except Exception as e:
            log.error(f"[RECORDING_SERVICE] Error getting Twilio credentials: {e}")
            return None
        
        # ✅ Use EXACT same logic as UI (routes_calls.py download_recording)
        # This is the single source of truth for downloading recordings
        try:
            recording_content = _download_from_twilio(
                call_log.recording_url,
                account_sid,
                auth_token,
                call_sid
            )
        except Exception as e:
            log.error(f"[RECORDING_SERVICE] Exception during Twilio download for {call_sid}: {e}")
            return None
        
        if not recording_content:
            log.error(f"[RECORDING_SERVICE] Failed to download recording for {call_sid}")
            return None
        
        # 3. Save to local disk
        try:
            with open(local_path, "wb") as f:
                f.write(recording_content)
            
            download_time = time.time() - download_start
            log.info(f"[RECORDING_SERVICE] ✅ Recording saved: {local_path} ({len(recording_content)} bytes) - took {download_time:.2f}s")
            
            if download_time > 10:
                log.warning(f"[RECORDING_SERVICE] ⚠️  Slow download detected ({download_time:.2f}s) - consider pre-downloading in webhook/worker to avoid 502")
            
            return local_path
            
        except Exception as e:
            log.error(f"[RECORDING_SERVICE] Failed to save recording to disk: {e}")
            return None
    
    finally:
        # Always release file lock and cleanup
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            except Exception as e:
                log.debug(f"[RECORDING_SERVICE] Error releasing lock: {e}")
            
            # Clean up lock file if it exists
            try:
                if os.path.exists(lock_file_path):
                    os.remove(lock_file_path)
            except Exception as e:
                log.debug(f"[RECORDING_SERVICE] Error removing lock file: {e}")


def _download_from_twilio(recording_url: str, account_sid: str, auth_token: str, call_sid: str) -> Optional[bytes]:
    """
    ✅ BUILD 342: Download recording in best quality format
    Priority: Dual-channel WAV > Mono WAV > MP3
    
    Dual-channel provides:
    - Separate tracks for customer/bot (cleaner transcription)
    - Less TTS "bleeding" into customer transcript
    - Higher quality audio (WAV > MP3)
    
    Args:
        recording_url: URL from CallLog.recording_url
        account_sid: Twilio account SID
        auth_token: Twilio auth token
        call_sid: Call SID for logging
        
    Returns:
        bytes: Recording content, or None if failed
    """
    try:
        # 🔥 FIX 502: Validate inputs before attempting download
        if not recording_url:
            log.error(f"[RECORDING_SERVICE] Missing recording_url for call_sid={call_sid}")
            return None
        if not account_sid:
            log.error(f"[RECORDING_SERVICE] Missing TWILIO_ACCOUNT_SID for call_sid={call_sid}")
            return None
        if not auth_token:
            log.error(f"[RECORDING_SERVICE] Missing TWILIO_AUTH_TOKEN for call_sid={call_sid}")
            return None
        
        # Handle .json URLs from Twilio properly (same as UI)
        base_url = recording_url
        if base_url.endswith(".json"):
            base_url = base_url[:-5]
        
        # Convert relative URL to absolute (if needed)
        if not base_url.startswith("http"):
            base_url = f"https://api.twilio.com{base_url}"
        
        # 🔥 BUILD 342: Try best quality first - Dual-channel WAV > Mono WAV > MP3
        # RequestedChannels=2 gives separate tracks for customer/bot (when available)
        urls_to_try = [
            (f"{base_url}.wav?RequestedChannels=2", "Dual-channel WAV (best quality)"),
            (f"{base_url}.wav", "Mono WAV (high quality)"),
            (f"{base_url}.mp3", "MP3 (fallback)"),
            (base_url, "Default format (last resort)"),
        ]
        
        auth = (account_sid, auth_token)
        last_error = None
        
        for attempt, (try_url, format_desc) in enumerate(urls_to_try, 1):
            try:
                log.debug(f"[RECORDING_SERVICE] Trying format {attempt}/{len(urls_to_try)}: {format_desc}")
                log.debug(f"[RECORDING_SERVICE] URL: {try_url[:80]}...")
                
                # 🔥 FIX 502: Add timeout to prevent hanging requests
                response = requests.get(try_url, auth=auth, timeout=30)
                
                log.debug(f"[RECORDING_SERVICE] Status: {response.status_code}, bytes: {len(response.content)}")
                
                # Check for 404 - might need to wait for Twilio processing
                if response.status_code == 404:
                    if attempt == 1:
                        log.debug("[RECORDING_SERVICE] Got 404, waiting 5s before next format...")
                        time.sleep(5)
                    continue
                
                # 🔥 FIX 502: Handle other error codes explicitly
                if response.status_code == 401:
                    log.error(f"[RECORDING_SERVICE] Authentication failed (401) for {call_sid}")
                    return None
                elif response.status_code == 403:
                    log.error(f"[RECORDING_SERVICE] Access forbidden (403) for {call_sid}")
                    return None
                elif response.status_code >= 500:
                    log.warning(f"[RECORDING_SERVICE] Twilio server error ({response.status_code}) for {call_sid}")
                    if attempt < len(urls_to_try):
                        continue  # Try next format
                    return None
                
                # Success!
                if response.status_code == 200 and len(response.content) > 1000:
                    log.info(f"[RECORDING_SERVICE] ✅ Successfully downloaded {len(response.content)} bytes using {format_desc}")
                    return response.content
                else:
                    log.debug(f"[RECORDING_SERVICE] URL returned {response.status_code} or too small ({len(response.content)} bytes)")
                    
            except requests.Timeout as e:
                log.warning(f"[RECORDING_SERVICE] Timeout downloading from Twilio for {call_sid}: {e}")
                last_error = e
                continue
            except requests.RequestException as e:
                log.debug(f"[RECORDING_SERVICE] Failed URL: {e}")
                last_error = e
                continue
            except Exception as e:
                log.error(f"[RECORDING_SERVICE] Unexpected error during download attempt: {e}")
                last_error = e
                continue
        
        # All attempts failed
        log.error(f"[RECORDING_SERVICE] All download attempts failed for {call_sid}. Last error: {last_error}")
        return None
        
    except Exception as e:
        log.error(f"[RECORDING_SERVICE] Download error for {call_sid}: {e}")
        return None


def check_local_recording_exists(call_sid: str) -> bool:
    """בדיקה מהירה אם קיימת הקלטה מקומית"""
    recordings_dir = _get_recordings_dir()
    local_path = os.path.join(recordings_dir, f"{call_sid}.mp3")
    return os.path.exists(local_path) and os.path.getsize(local_path) > 1000
