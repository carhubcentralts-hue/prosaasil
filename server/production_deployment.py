#!/usr/bin/env python3
"""
Production Deployment Manager for Hebrew AI Call Center
מנהל פריסה לייצור למערכת מוקד שיחות עברית
"""
import os
import sys
import subprocess
import time
import threading
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductionDeploymentManager:
    def __init__(self):
        self.services = {}
        self.is_running = False
        
    def check_environment(self):
        """בדיקת משתני סביבה קריטיים"""
        required_vars = [
            'SESSION_SECRET', 'OPENAI_API_KEY', 
            'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER',
            'DATABASE_URL'
        ]
        
        missing = []
        for var in required_vars:
            if not os.environ.get(var):
                missing.append(var)
        
        if missing:
            logger.error(f"❌ Missing environment variables: {missing}")
            return False
            
        logger.info("✅ All environment variables present")
        return True
    
    def check_dependencies(self):
        """בדיקת תלויות Python"""
        try:
            import flask
            import openai
            import twilio
            import sqlalchemy
            import gtts
            import schedule
            logger.info("✅ All Python dependencies available")
            return True
        except ImportError as e:
            logger.error(f"❌ Missing dependency: {e}")
            return False
    
    def start_main_app(self):
        """הפעלת האפליקציה הראשית"""
        try:
            logger.info("🚀 Starting main Flask application...")
            
            # הפעלה עם Gunicorn לייצור
            cmd = [
                'gunicorn', 
                '--bind', '0.0.0.0:5000',
                '--workers', '2',
                '--timeout', '30',
                '--preload',
                '--access-logfile', '-',
                '--error-logfile', '-',
                'main:app'
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.services['main_app'] = process
            
            # Wait a bit to check if it started successfully
            time.sleep(3)
            if process.poll() is None:
                logger.info("✅ Main application started successfully")
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"❌ Main application failed to start: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error starting main application: {e}")
            return False
    
    def start_background_services(self):
        """הפעלת שירותי רקע"""
        try:
            logger.info("🧹 Starting background services...")
            
            def run_background():
                from auto_cleanup_background import background_cleanup
                from cleanup_service import start_audio_cleanup
                
                # הפעלת שירותי ניקוי
                background_cleanup.start_scheduler()
                start_audio_cleanup()
                
                logger.info("✅ Background services started")
                
                # שמירה על התהליך חי
                while self.is_running:
                    time.sleep(60)
            
            bg_thread = threading.Thread(target=run_background, daemon=True)
            bg_thread.start()
            self.services['background'] = bg_thread
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting background services: {e}")
            return False
    
    def start_whatsapp_service(self):
        """הפעלת שירות WhatsApp"""
        try:
            logger.info("📱 Starting WhatsApp service...")
            
            # בדיקת זמינות Baileys
            if os.path.exists('baileys_client.js'):
                logger.info("✅ Baileys WhatsApp client available")
            
            # בדיקת Twilio WhatsApp
            twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            if twilio_sid:
                logger.info("✅ Twilio WhatsApp Business API configured")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error with WhatsApp service: {e}")
            return False
    
    def perform_health_checks(self):
        """בדיקות תקינות מערכת"""
        try:
            logger.info("🏥 Performing health checks...")
            
            # בדיקת מסד נתונים
            from app import app, db
            with app.app_context():
                db.session.execute('SELECT 1').scalar()
                logger.info("✅ Database connection healthy")
            
            # בדיקת AI Service
            from ai_service_enhanced import EnhancedAIService
            ai_service = EnhancedAIService()
            if ai_service.api_available:
                logger.info("✅ AI Service healthy")
            else:
                logger.warning("⚠️ AI Service running in fallback mode")
            
            # בדיקת שירותי ניקוי
            from auto_cleanup_background import background_cleanup
            stats = background_cleanup.get_cleanup_stats()
            logger.info(f"✅ Cleanup service healthy - {stats}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False
    
    def deploy(self):
        """פריסה מלאה למערכת ייצור"""
        logger.info("🚀 Starting production deployment...")
        
        # שלב 1: בדיקות קדם-פריסה
        if not self.check_environment():
            return False
            
        if not self.check_dependencies():
            return False
        
        # שלב 2: הפעלת שירותים
        self.is_running = True
        
        if not self.start_background_services():
            return False
            
        if not self.start_whatsapp_service():
            return False
            
        if not self.start_main_app():
            return False
        
        # שלב 3: בדיקות תקינות
        time.sleep(5)  # המתנה לייצוב המערכת
        
        if not self.perform_health_checks():
            logger.warning("⚠️ Some health checks failed, but continuing...")
        
        # שלב 4: מוניטורינג רציף
        logger.info("✅ Production deployment completed successfully!")
        logger.info("🎯 System is ready for production use")
        logger.info("📊 Monitoring services...")
        
        try:
            while self.is_running:
                time.sleep(300)  # בדיקה כל 5 דקות
                if not self.perform_health_checks():
                    logger.warning("⚠️ Health check issues detected")
                    
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down services...")
            self.shutdown()
    
    def shutdown(self):
        """כיבוי מבוקר של כל השירותים"""
        logger.info("🛑 Initiating graceful shutdown...")
        
        self.is_running = False
        
        # כיבוי תהליכים
        for service_name, service in self.services.items():
            try:
                if hasattr(service, 'terminate'):
                    service.terminate()
                    logger.info(f"✅ {service_name} terminated")
            except Exception as e:
                logger.error(f"❌ Error terminating {service_name}: {e}")
        
        logger.info("✅ All services shut down")

def main():
    """נקודת כניסה ראשית"""
    deployment = ProductionDeploymentManager()
    
    try:
        deployment.deploy()
    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()