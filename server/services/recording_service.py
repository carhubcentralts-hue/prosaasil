"""
Recording Service - שירות מאוחד להורדה ושמירה של הקלטות
משמש גם ל-UI וגם ל-offline worker - single source of truth
"""
import os
import logging
import requests
import time
from typing import Optional
from server.models_sql import CallLog
from flask import current_app, has_app_context

log = logging.getLogger(__name__)

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
    if not call_log or not call_log.call_sid:
        log.error("[RECORDING_SERVICE] Invalid call_log provided")
        return None
    
    call_sid = call_log.call_sid
    
    # 1. Check if we already have the file locally
    recordings_dir = _get_recordings_dir()
    os.makedirs(recordings_dir, exist_ok=True)
    local_path = os.path.join(recordings_dir, f"{call_sid}.mp3")
    
    if os.path.exists(local_path):
        file_size = os.path.getsize(local_path)
        if file_size > 1000:  # Valid file (>1KB)
            log.info(f"[RECORDING_SERVICE] ✅ Using existing local file: {local_path} ({file_size} bytes)")
            print(f"[RECORDING_SERVICE] ✅ Using existing recording from disk for {call_sid}")
            return local_path
        else:
            log.warning(f"[RECORDING_SERVICE] Local file too small ({file_size} bytes), will re-download")
            os.remove(local_path)
    
    # 2. Download from Twilio using call_log.recording_url
    if not call_log.recording_url:
        log.error(f"[RECORDING_SERVICE] No recording_url for call {call_sid}")
        print(f"❌ [RECORDING_SERVICE] No recording_url for {call_sid}")
        return None
    
    log.info(f"[RECORDING_SERVICE] Downloading recording from Twilio for {call_sid}")
    print(f"[RECORDING_SERVICE] Downloading recording from Twilio for {call_sid}")
    
    # Get Twilio credentials
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    
    if not account_sid or not auth_token:
        log.error("[RECORDING_SERVICE] Missing Twilio credentials")
        print("❌ [RECORDING_SERVICE] Missing Twilio credentials")
        return None
    
    # ✅ Use EXACT same logic as UI (routes_calls.py download_recording)
    # This is the single source of truth for downloading recordings
    recording_content = _download_from_twilio(
        call_log.recording_url,
        account_sid,
        auth_token,
        call_sid
    )
    
    if not recording_content:
        log.error(f"[RECORDING_SERVICE] Failed to download recording for {call_sid}")
        print(f"❌ [RECORDING_SERVICE] Failed to download recording for {call_sid}")
        return None
    
    # 3. Save to local disk
    try:
        with open(local_path, "wb") as f:
            f.write(recording_content)
        
        log.info(f"[RECORDING_SERVICE] ✅ Recording saved: {local_path} ({len(recording_content)} bytes)")
        print(f"[RECORDING_SERVICE] ✅ Recording saved to disk: {local_path} ({len(recording_content)} bytes)")
        return local_path
        
    except Exception as e:
        log.error(f"[RECORDING_SERVICE] Failed to save recording to disk: {e}")
        print(f"❌ [RECORDING_SERVICE] Failed to save recording to disk: {e}")
        return None


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
                log.info(f"[RECORDING_SERVICE] Trying format {attempt}/{len(urls_to_try)}: {format_desc}")
                log.info(f"[RECORDING_SERVICE] URL: {try_url[:80]}...")
                print(f"[RECORDING_SERVICE] Trying {format_desc}")
                
                response = requests.get(try_url, auth=auth, timeout=30)
                
                log.info(f"[RECORDING_SERVICE] Status: {response.status_code}, bytes: {len(response.content)}")
                print(f"[RECORDING_SERVICE] Status: {response.status_code}, bytes: {len(response.content)}")
                
                # Check for 404 - might need to wait for Twilio processing
                if response.status_code == 404:
                    if attempt == 1:
                        log.info("[RECORDING_SERVICE] Got 404, waiting 5s before next format...")
                        print("[RECORDING_SERVICE] Got 404, waiting 5s...")
                        time.sleep(5)
                    continue
                
                # Success!
                if response.status_code == 200 and len(response.content) > 1000:
                    log.info(f"[RECORDING_SERVICE] ✅ Successfully downloaded {len(response.content)} bytes using {format_desc}")
                    print(f"[RECORDING_SERVICE] ✅ Downloaded {len(response.content)} bytes using {format_desc}")
                    return response.content
                else:
                    log.warning(f"[RECORDING_SERVICE] URL returned {response.status_code} or too small ({len(response.content)} bytes)")
                    
            except requests.RequestException as e:
                log.warning(f"[RECORDING_SERVICE] Failed URL: {e}")
                last_error = e
                continue
        
        # All attempts failed
        log.error(f"[RECORDING_SERVICE] All download attempts failed for {call_sid}. Last error: {last_error}")
        print(f"❌ [RECORDING_SERVICE] All download attempts failed for {call_sid}")
        return None
        
    except Exception as e:
        log.error(f"[RECORDING_SERVICE] Download error for {call_sid}: {e}")
        print(f"❌ [RECORDING_SERVICE] Download error: {e}")
        return None


def check_local_recording_exists(call_sid: str) -> bool:
    """בדיקה מהירה אם קיימת הקלטה מקומית"""
    recordings_dir = _get_recordings_dir()
    local_path = os.path.join(recordings_dir, f"{call_sid}.mp3")
    return os.path.exists(local_path) and os.path.getsize(local_path) > 1000
