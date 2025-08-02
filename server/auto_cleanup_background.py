"""
Background Auto-Cleanup Service
שירות ניקוי אוטומטי ברקע עם מוניטורינג
"""
import schedule
import time
import threading
import logging
from datetime import datetime, timedelta
import os
import glob

logger = logging.getLogger(__name__)

class BackgroundCleanupService:
    def __init__(self):
        self.is_running = False
        self.cleanup_stats = {
            'last_cleanup': None,
            'files_deleted_today': 0,
            'files_deleted_week': 0,
            'total_space_freed_mb': 0
        }
        
    def cleanup_audio_files(self):
        """ניקוי קבצי אודיו ישנים"""
        try:
            # נקה קבצי TTS ישנים מ-24 שעות
            audio_dir = 'static/voice_responses'
            if not os.path.exists(audio_dir):
                return
            
            cutoff_time = datetime.now() - timedelta(hours=24)
            deleted_count = 0
            space_freed = 0
            
            for audio_file in glob.glob(f"{audio_dir}/*.mp3"):
                try:
                    file_time = datetime.fromtimestamp(os.path.getctime(audio_file))
                    if file_time < cutoff_time:
                        file_size = os.path.getsize(audio_file)
                        os.remove(audio_file)
                        deleted_count += 1
                        space_freed += file_size
                        
                except Exception as e:
                    logger.error(f"Error deleting file {audio_file}: {e}")
            
            # עדכון סטטיסטיקות
            self.cleanup_stats['last_cleanup'] = datetime.now()
            self.cleanup_stats['files_deleted_today'] += deleted_count
            self.cleanup_stats['total_space_freed_mb'] += space_freed / (1024 * 1024)
            
            logger.info(f"🧹 Cleanup completed: {deleted_count} files, {space_freed/1024/1024:.2f}MB freed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def cleanup_old_logs(self):
        """ניקוי לוגים ישנים"""
        try:
            log_files = glob.glob("*.log")
            cutoff_time = datetime.now() - timedelta(days=7)
            
            for log_file in log_files:
                try:
                    file_time = datetime.fromtimestamp(os.path.getctime(log_file))
                    if file_time < cutoff_time and os.path.getsize(log_file) > 50 * 1024 * 1024:  # 50MB
                        os.remove(log_file)
                        logger.info(f"Deleted old log: {log_file}")
                except Exception as e:
                    logger.error(f"Error deleting log {log_file}: {e}")
                    
        except Exception as e:
            logger.error(f"Log cleanup error: {e}")
    
    def reset_daily_stats(self):
        """איפוס סטטיסטיקות יומיות"""
        self.cleanup_stats['files_deleted_week'] += self.cleanup_stats['files_deleted_today']
        self.cleanup_stats['files_deleted_today'] = 0
        logger.info("Daily cleanup stats reset")
    
    def reset_weekly_stats(self):
        """איפוס סטטיסטיקות שבועיות"""
        self.cleanup_stats['files_deleted_week'] = 0
        logger.info("Weekly cleanup stats reset")
        
    def get_cleanup_stats(self):
        """קבלת סטטיסטיקות ניקוי"""
        return self.cleanup_stats.copy()
    
    def start_scheduler(self):
        """הפעלת מתזמן הניקוי"""
        if self.is_running:
            return
            
        # תזמון המשימות
        schedule.every(6).hours.do(self.cleanup_audio_files)
        schedule.every().day.at("02:00").do(self.cleanup_old_logs)
        schedule.every().day.at("00:01").do(self.reset_daily_stats)
        schedule.every().sunday.at("00:00").do(self.reset_weekly_stats)
        
        self.is_running = True
        logger.info("🧹 Background cleanup scheduler started")
        
        # הרצה ב-thread נפרד
        def run_scheduler():
            while self.is_running:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # בדיקה כל דקה
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")
                    time.sleep(60)
        
        cleanup_thread = threading.Thread(target=run_scheduler, daemon=True)
        cleanup_thread.start()
        
    def stop_scheduler(self):
        """עצירת מתזמן הניקוי"""
        self.is_running = False
        schedule.clear()
        logger.info("Background cleanup scheduler stopped")

# יצירת אינסטנס גלובלי
background_cleanup = BackgroundCleanupService()