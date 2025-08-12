#!/usr/bin/env python3
"""
Final Clean App - אפליקציה מלאה ונקייה עם כל המערכות
"""

import os
import logging
from flask import Flask
from flask_cors import CORS
from app_clean import create_clean_app
from routes_clean import clean_twilio_bp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

def create_final_app():
    """יצירת אפליקציה מלאה ונקייה"""
    
    # Create clean base app
    app = create_clean_app()
    
    # Register clean Twilio routes
    app.register_blueprint(clean_twilio_bp)
    
    logger.info("✅ Clean Twilio webhooks registered successfully")
    
    @app.route("/", methods=['GET'])
    def health_check():
        """בדיקת תקינות המערכת"""
        return {
            'status': 'success',
            'message': 'Hebrew AI Call Center System - Ready!',
            'business': 'שי דירות ומשרדים בע״מ',
            'phone': '+972-3-555-7777',
            'webhooks': {
                'incoming_call': '/webhook/incoming_call',
                'handle_recording': '/webhook/handle_recording'
            },
            'features': [
                'Hebrew AI conversations',
                'OpenAI GPT-4o responses', 
                'Whisper transcription',
                'Real estate expertise',
                'Conversation logging'
            ]
        }
    
    return app

# Create the final clean app
app = create_final_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(
        debug=False,
        host="0.0.0.0", 
        port=port,
        threaded=True
    )