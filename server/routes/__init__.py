"""
AgentLocator v42 - Centralized Blueprint Registration
ריכוז כל ה-Blueprints במיקום אחד
"""

from .routes_twilio import twilio_bp
from .routes_timeline import timeline_bp
from .routes_signature import signature_bp
from .routes_calendar import calendar_bp
from .routes_proposal import proposal_bp
from .routes_reports import reports_bp

def register_blueprints(app):
    """רישום כל ה-Blueprints עם URL prefixes נכונים"""
    
    # Twilio webhooks - חובה להיות ב-/webhook
    app.register_blueprint(twilio_bp, url_prefix="/webhook")
    
    # Timeline API - מאוחד לכל הלקוחות
    app.register_blueprint(timeline_bp, url_prefix="/api")
    
    # Digital signatures - חתימות דיגיטליות
    app.register_blueprint(signature_bp, url_prefix="/api/signature")
    
    # Calendar integration - יומן ופגישות
    app.register_blueprint(calendar_bp, url_prefix="/api/calendar")
    
    # Proposals & quotes - הצעות מחיר
    app.register_blueprint(proposal_bp, url_prefix="/api/proposal")
    
    # Analytics & reports - דוחות ואנליטיקות
    app.register_blueprint(reports_bp, url_prefix="/api/reports")
    
    print("✅ All AgentLocator v42 Blueprints registered successfully")