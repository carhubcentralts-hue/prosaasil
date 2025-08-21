# server/routes/__init__.py
"""
Clean routes organization - only existing files
"""

def register_all_blueprints(app):
    """Register only existing application blueprints"""
    
    blueprints = []
    
    # Core Twilio webhooks (required for calls)
    try:
        from server.routes_twilio import twilio_bp
        blueprints.append(("Twilio Webhooks", twilio_bp))
    except ImportError as e:
        app.logger.error("Critical: Twilio routes missing: %s", e)
    
    # Health check routes
    try:
        from server.health_routes import health_bp
        blueprints.append(("Health", health_bp))
    except ImportError:
        pass  # Optional
    
    # Authentication routes  
    try:
        from server.auth_routes import auth_bp
        blueprints.append(("Authentication", auth_bp))
    except ImportError:
        pass  # Optional
    
    # Available APIs
    try:
        from server.api_crm_unified import crm_bp
        blueprints.append(("CRM", crm_bp))
    except ImportError:
        pass
    
    try:
        from server.api_business import biz_bp
        blueprints.append(("Business", biz_bp))
    except ImportError:
        pass
    
    try:
        from server.api_timeline import timeline_bp
        blueprints.append(("Timeline", timeline_bp))
    except ImportError:
        pass
    
    # Register all blueprints
    registered = 0
    for name, bp in blueprints:
        try:
            app.register_blueprint(bp)
            app.logger.info("✅ %s registered", name)
            registered += 1
        except Exception as e:
            app.logger.error("❌ %s failed: %s", name, e)
    
    app.logger.info("🎯 %d blueprints registered", registered)
    return registered