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
    
    # Health and auth routes are handled by app_factory.py directly
    
    # Available APIs
    try:
        from server.routes_crm import crm_bp
        blueprints.append(("CRM", crm_bp))
    except ImportError:
        pass
    
    # Business and timeline APIs removed - functionality integrated into main routes
    
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