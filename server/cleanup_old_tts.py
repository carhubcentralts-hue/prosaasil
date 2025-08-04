#!/usr/bin/env python3
"""
Cleanup script for old TTS files
מנוקה קבצי TTS ישנים מעל 3 ימים
"""

import os
import time
import logging
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('cleanup_tts')

def cleanup_old_tts_files():
    """מנקה קבצי TTS ישנים מעל 3 ימים"""
    try:
        tts_dir = "server/static/voice_responses"
        if not os.path.exists(tts_dir):
            logger.warning(f"TTS directory not found: {tts_dir}")
            return
        
        # מציאת קבצים ישנים מעל 3 ימים
        cutoff_time = time.time() - (3 * 24 * 60 * 60)  # 3 days ago
        files_deleted = 0
        total_size_deleted = 0
        
        for filename in os.listdir(tts_dir):
            if filename.endswith('.mp3'):
                filepath = os.path.join(tts_dir, filename)
                file_time = os.path.getmtime(filepath)
                
                if file_time < cutoff_time:
                    try:
                        file_size = os.path.getsize(filepath)
                        os.remove(filepath)
                        files_deleted += 1
                        total_size_deleted += file_size
                        logger.info(f"🗑️ Deleted old TTS file: {filename}")
                    except Exception as e:
                        logger.error(f"Failed to delete {filename}: {e}")
        
        logger.info(f"🧹 Cleanup completed: {files_deleted} files deleted, {total_size_deleted/1024:.1f}KB freed")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

if __name__ == "__main__":
    cleanup_old_tts_files()