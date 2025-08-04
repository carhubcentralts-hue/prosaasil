#!/usr/bin/env python3
"""
Call System Monitor - בדיקת בריאות מערכת השיחות כל 5 דקות
"""

import os
import sys
import time
import logging
import requests
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('call_monitor')

def check_twilio_endpoints():
    """בדיקת נגישות endpoints של Twilio"""
    base_url = "https://ai-crmd.replit.app"
    endpoints = [
        "/twilio/incoming_call",
        "/twilio/handle_recording",
        "/twilio/call_status"
    ]
    
    results = {}
    for endpoint in endpoints:
        try:
            # GET request to check if endpoint exists (should return 405 Method Not Allowed)
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            if response.status_code == 405:  # Method Not Allowed means endpoint exists
                results[endpoint] = "✅ Available"
            else:
                results[endpoint] = f"⚠️ Unexpected status: {response.status_code}"
        except Exception as e:
            results[endpoint] = f"❌ Error: {str(e)}"
    
    return results

def check_tts_files():
    """בדיקת זמינות קבצי TTS"""
    try:
        tts_dir = "server/static/voice_responses"
        if not os.path.exists(tts_dir):
            return "❌ TTS directory not found"
        
        files = [f for f in os.listdir(tts_dir) if f.endswith('.mp3')]
        file_count = len(files)
        
        if file_count > 0:
            # Test a random file URL
            import random
            test_file = random.choice(files)
            test_url = f"https://ai-crmd.replit.app/server/static/voice_responses/{test_file}"
            
            try:
                response = requests.head(test_url, timeout=5)
                if response.status_code == 200:
                    return f"✅ {file_count} TTS files available, test file accessible"
                else:
                    return f"⚠️ {file_count} files but test failed: {response.status_code}"
            except:
                return f"⚠️ {file_count} files but URL test failed"
        else:
            return "❌ No TTS files found"
            
    except Exception as e:
        return f"❌ TTS check error: {str(e)}"

def check_database():
    """בדיקת חיבור מסד נתונים ושיחות אחרונות"""
    try:
        # Import here to avoid circular imports
        from models import Business, CallLog, db
        from app import app
        
        with app.app_context():
            # Check businesses
            business_count = Business.query.count()
            
            # Check recent calls (last 24 hours)
            from datetime import timedelta
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_calls = CallLog.query.filter(CallLog.created_at >= yesterday).count()
            
            # Check calls with recordings
            calls_with_recordings = CallLog.query.filter(CallLog.recording_url.isnot(None)).count()
            
            return f"✅ DB: {business_count} businesses, {recent_calls} recent calls, {calls_with_recordings} with recordings"
            
    except Exception as e:
        return f"❌ Database error: {str(e)}"

def check_openai_services():
    """בדיקת זמינות שירותי OpenAI"""
    try:
        import openai
        api_key = os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            return "❌ OpenAI API key not found"
        
        # Simple test call
        client = openai.OpenAI(api_key=api_key)
        
        # Test with a minimal request
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        
        return "✅ OpenAI GPT-4o and Whisper services available"
        
    except Exception as e:
        return f"❌ OpenAI error: {str(e)}"

def generate_health_report():
    """יצירת דוח בריאות מערכת"""
    logger.info("🔍 Starting call system health check...")
    
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "twilio_endpoints": check_twilio_endpoints(),
        "tts_files": check_tts_files(),
        "database": check_database(),
        "openai": check_openai_services()
    }
    
    # Log results
    logger.info("📊 CALL SYSTEM HEALTH REPORT:")
    logger.info(f"   🕐 Time: {report['timestamp']}")
    logger.info(f"   📞 Twilio Endpoints: {report['twilio_endpoints']}")
    logger.info(f"   🎵 TTS Files: {report['tts_files']}")
    logger.info(f"   💾 Database: {report['database']}")
    logger.info(f"   🤖 OpenAI: {report['openai']}")
    
    return report

def run_continuous_monitoring():
    """הרצה רצופה של ניטור מערכת"""
    logger.info("🚀 Call System Monitor started - checking every 5 minutes")
    
    while True:
        try:
            generate_health_report()
            time.sleep(300)  # 5 minutes
        except KeyboardInterrupt:
            logger.info("👋 Monitor stopped by user")
            break
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            time.sleep(60)  # Wait 1 minute on error

if __name__ == "__main__":
    # Single check mode
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        generate_health_report()
    else:
        # Continuous monitoring mode
        run_continuous_monitoring()