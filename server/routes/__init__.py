from routes.routes_twilio import twilio_bp
from routes.routes_crm import crm_bp
from routes.routes_signature import signature_bp
from routes.routes_calendar import calendar_bp
from routes.routes_proposal import proposal_bp
from routes.routes_reports import reports_bp

def register_blueprints(app):
    app.register_blueprint(twilio_bp,    url_prefix="/webhook")
    app.register_blueprint(crm_bp,       url_prefix="/api/crm")
    app.register_blueprint(signature_bp, url_prefix="/signature")
    app.register_blueprint(calendar_bp,  url_prefix="/calendar")
    app.register_blueprint(proposal_bp,  url_prefix="/proposal")
    app.register_blueprint(reports_bp,   url_prefix="/reports")