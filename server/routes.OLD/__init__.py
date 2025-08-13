def register_blueprints(app):
    try:
        from ..routes_twilio import twilio_bp
        app.register_blueprint(twilio_bp)
    except ImportError:
        print("Warning: Could not import twilio_bp")
    
    try:
        from ..api_timeline import timeline_bp
        app.register_blueprint(timeline_bp)
    except ImportError:
        print("Warning: Could not import timeline_bp")