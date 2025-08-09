def register_blueprints(app):
    # Import auth blueprint first
    try:
        from ..auth_bp import auth_bp
        app.register_blueprint(auth_bp)
    except ImportError:
        pass
    
    # Import frontend - serves React app
    try:
        from .frontend import frontend_bp
        app.register_blueprint(frontend_bp)
    except ImportError:
        pass
    
    # Import only existing blueprints
    try:
        from ..routes_twilio import twilio_bp
        app.register_blueprint(twilio_bp, url_prefix="/webhook")
    except ImportError:
        pass
    
    try:
        from ..auth import auth_bp as old_auth_bp
        app.register_blueprint(old_auth_bp, url_prefix="/auth")
    except ImportError:
        pass
        
    try:
        from ..api_admin_stats import admin_stats_bp
        app.register_blueprint(admin_stats_bp)
    except ImportError:
        pass
        
    try:
        from ..api_business_stats import business_stats_bp
        app.register_blueprint(business_stats_bp)
    except ImportError:
        pass