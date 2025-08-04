#!/usr/bin/env python3
"""
Background Auto Cleanup Service
ניקוי אוטומטי של קבצי TTS ישנים - רץ ברקע
"""

import os
import time
import logging
import schedule
from cleanup_old_tts import cleanup_old_tts_files

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('auto_cleanup_background')

def run_cleanup_job():
    """הפעלת ניקוי קבצי TTS"""
    try:
        logger.info("🧹 Starting scheduled TTS cleanup...")
        cleanup_old_tts_files()
        logger.info("✅ Scheduled cleanup completed")
    except Exception as e:
        logger.error(f"❌ Cleanup job failed: {e}")

def start_background_scheduler():
    """הפעלת scheduler לניקוי אוטומטי"""
    # Schedule cleanup every 6 hours
    schedule.every(6).hours.do(run_cleanup_job)
    
    # Also run cleanup daily at 2 AM
    schedule.every().day.at("02:00").do(run_cleanup_job)
    
    logger.info("🧹 Background cleanup scheduler started")
    logger.info("📅 Cleanup scheduled: every 6 hours + daily at 2 AM")
    
    # Run cleanup immediately on startup
    run_cleanup_job()
    
    # Keep scheduler running
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("👋 Background cleanup stopped")
            break
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            time.sleep(300)  # Wait 5 minutes on error

if __name__ == "__main__":
    start_background_scheduler()