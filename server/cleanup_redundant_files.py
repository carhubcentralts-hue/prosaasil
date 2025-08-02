#!/usr/bin/env python3
"""
Cleanup Redundant Files for Production
ניקוי קבצים מיותרים לייצור
"""
import os
import shutil
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductionCleanup:
    def __init__(self):
        self.removed_count = 0
        self.cleaned_dirs = []
        
    def remove_file_safe(self, file_path):
        """הסרת קובץ בטוחה"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.removed_count += 1
                logger.info(f"🗑️ Removed: {file_path}")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Could not remove {file_path}: {e}")
        return False
    
    def remove_dir_safe(self, dir_path):
        """הסרת תיקייה בטוחה"""
        try:
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                shutil.rmtree(dir_path)
                self.cleaned_dirs.append(dir_path)
                logger.info(f"📁 Removed directory: {dir_path}")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Could not remove directory {dir_path}: {e}")
        return False
    
    def cleanup_documentation_duplicates(self):
        """ניקוי מסמכים כפולים"""
        docs_to_remove = [
            'BAILEYS_READY_TO_RUN.md',
            'BAILEYS_SETUP_GUIDE.md', 
            'CRM_ENHANCEMENTS_COMPLETE.md',
            'CRM_FINAL_SUCCESS_REPORT.md',
            'CRM_SYSTEM_VERIFICATION_COMPLETE.md',
            'STEP_BY_STEP_BAILEYS.md',
            'SYSTEM_ACCESS_GUIDE.md',
            'SYSTEM_VERIFICATION_COMPLETE.md',
            'TWILIO_11200_FIXED.md',
            'TWILIO_FIXES_COMPLETE.md',
            'VERIFICATION_SETUP_COMPLETE.md',
            'WHATSAPP_ACCOUNT_STATUS_UPDATE.md',
            'WHATSAPP_ACCOUNT_UNLOCK_INSTRUCTIONS.md',
            'WHATSAPP_CONVERSATION_READY.md',
            'WHATSAPP_FINAL_ENHANCEMENT.md',
            'WHATSAPP_SETUP_INSTRUCTIONS.md',
            'WHATSAPP_SYSTEM_COMPLETE.md',
            'WHATSAPP_TROUBLESHOOT.md',
            'WHATSAPP_TROUBLESHOOT_FINAL.md',
            'WHATSAPP_VERIFICATION_COMPLETE.md',
            'setup_whatsapp.md',
            'final_test_summary.md',
            'איך_לפתוח_טרמינל.md'
        ]
        
        for doc in docs_to_remove:
            self.remove_file_safe(doc)
    
    def cleanup_test_files(self):
        """ניקוי קבצי בדיקה"""
        test_files = [
            'test_recording.txt',
            'test_report.txt',
            'test_whatsapp_system.py',
            'end_to_end_test.py',
            'live_system_test.py',
            'comprehensive_test_suite.py',
            'cleanup_report.txt',
            'temp_status.html',
            'cookies.txt'
        ]
        
        for test_file in test_files:
            self.remove_file_safe(test_file)
    
    def cleanup_duplicate_python_files(self):
        """ניקוי קבצי Python כפולים"""
        duplicates = [
            'FINAL_WORKING_SOLUTION.py',
            'admin_dashboard_enhanced.py',
            'auto_cleanup.py',
            'auto_cleanup_enhanced.py',
            'background_processor.py',
            'baileys_setup.py',
            'business_permissions.py',
            'call_limiter.py',
            'cleanup_service.py',
            'conversation_tracker.py',
            'debug_logger.py',
            'enhanced_business_integration.py',
            'google_calendar_crm.py',
            'google_calendar_integration.py',
            'keyword_handler.py',
            'permissions.py',
            'production_checklist.py',
            'production_enhancements.py',
            'usage_monitor.py',
            'whatsapp_dashboard_enhanced.py',
            'whatsapp_status_webhook.py',
            'whatsapp_template_helper.py'
        ]
        
        for duplicate in duplicates:
            self.remove_file_safe(duplicate)
    
    def cleanup_node_modules_excess(self):
        """ניקוי עודפי node_modules"""
        # Keep only essential packages for Baileys
        essential_packages = {
            '@whiskeysockets/baileys',
            'qrcode-terminal',
            'ws'
        }
        
        node_modules_path = 'node_modules'
        if os.path.exists(node_modules_path):
            for item in os.listdir(node_modules_path):
                item_path = os.path.join(node_modules_path, item)
                if os.path.isdir(item_path) and item not in essential_packages:
                    # Don't remove, just log what could be removed
                    logger.info(f"📦 Could optimize: {item}")
    
    def cleanup_instance_databases(self):
        """ניקוי מסדי נתונים מיותרים"""
        instance_files = [
            'instance/app.db',
            'instance/project.db'
            # Keep call_center.db as it might be the main one
        ]
        
        for db_file in instance_files:
            self.remove_file_safe(db_file)
    
    def cleanup_attached_assets(self):
        """ניקוי נכסים מצורפים"""
        attached_assets_dir = 'attached_assets'
        if os.path.exists(attached_assets_dir):
            # המרת התיקייה כולה
            self.remove_dir_safe(attached_assets_dir)
    
    def cleanup_baileys_auth_partial(self):
        """ניקוי חלקי של auth baileys - שמירת הכרחיים"""
        baileys_dir = 'baileys_auth_info'
        if os.path.exists(baileys_dir):
            # Keep only essential files
            essential_files = {'creds.json', 'app-state-sync-key-AAAAAMPl.json'}
            
            for item in os.listdir(baileys_dir):
                if item not in essential_files:
                    item_path = os.path.join(baileys_dir, item)
                    self.remove_file_safe(item_path)
    
    def cleanup_logs_and_temp(self):
        """ניקוי לוגים וקבצים זמניים"""
        temp_files = [
            'usage_stats.json',
            'logs/access.log',
            'logs/error.log'
        ]
        
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                # Don't remove logs, just note them
                logger.info(f"📄 Log file exists: {temp_file}")
    
    def run_full_cleanup(self):
        """הרצת ניקוי מלא"""
        logger.info("🧹 Starting production cleanup...")
        
        # ניקוי בשלבים
        self.cleanup_documentation_duplicates()
        self.cleanup_test_files()
        self.cleanup_duplicate_python_files()
        self.cleanup_instance_databases()
        self.cleanup_attached_assets()
        self.cleanup_baileys_auth_partial()
        self.cleanup_logs_and_temp()
        self.cleanup_node_modules_excess()
        
        logger.info(f"✅ Cleanup completed!")
        logger.info(f"🗑️ Files removed: {self.removed_count}")
        logger.info(f"📁 Directories cleaned: {len(self.cleaned_dirs)}")
        
        # סיכום קבצים נותרים
        remaining_py_files = len([f for f in os.listdir('.') if f.endswith('.py')])
        logger.info(f"🐍 Python files remaining: {remaining_py_files}")
        
        return self.removed_count

if __name__ == "__main__":
    cleanup = ProductionCleanup()
    removed = cleanup.run_full_cleanup()
    
    if removed > 0:
        print(f"\n🎯 Production cleanup completed: {removed} files removed")
        print("✅ System is now optimized for deployment")
    else:
        print("\n✅ System already clean - ready for deployment")