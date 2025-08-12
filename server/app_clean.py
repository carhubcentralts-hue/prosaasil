#!/usr/bin/env python3
"""
Clean Flask App - אפליקציה נקייה ללא קונפליקטים
"""

import os
import logging
from flask import Flask
from flask_cors import CORS
from models_clean import db, CleanBusiness
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

def create_clean_app():
    """יצירת Flask app נקי"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-for-testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clean_hebrew_crm.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Initialize extensions
    CORS(app)
    db.init_app(app)
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Create main business if not exists
        existing_business = CleanBusiness.query.first()
        if not existing_business:
            business = CleanBusiness()
            business.name = 'שי דירות ומשרדים בע״מ'
            business.business_type = 'real_estate'
            business.phone = '+972-3-555-7777'
            business.email = 'info@shai-realestate.co.il'
            business.address = 'תל אביב, ישראל'
            business.is_active = True
            business.created_at = datetime.utcnow()
            
            db.session.add(business)
            db.session.commit()
            
            logger.info(f"✅ Clean business created: {business.name}")
        else:
            logger.info(f"✅ Business exists: {existing_business.name}")
    
    return app

# Create the app instance
app = create_clean_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)