# server/routes/__init__.py
"""
Professional routes organization following App Factory blueprint pattern
"""

def register_all_blueprints(app):
    """Register all application blueprints with professional error handling"""
    
    blueprints = []
    
    # Core system routes
    try:
        from server.health_routes import health_bp
        blueprints.append(("Health", health_bp))
    except ImportError as e:
        app.logger.warning("Health routes not available: %s", e)
    
    # Authentication
    try:
        from server.auth_routes import auth_bp
        blueprints.append(("Authentication", auth_bp))
    except ImportError as e:
        app.logger.error("Authentication routes missing: %s", e)
    
    # Twilio voice webhooks (no auth required)
    try:
        from server.routes_twilio import twilio_bp
        blueprints.append(("Twilio Webhooks", twilio_bp))
    except ImportError:
        try:
            from server.routes_twilio_improved import twilio_bp
            blueprints.append(("Twilio Webhooks Enhanced", twilio_bp))
        except ImportError as e:
            app.logger.error("No Twilio webhook routes available: %s", e)
    
    # Business APIs (auth required)
    try:
        from server.api_crm_improved import crm_bp
        blueprints.append(("CRM", crm_bp))
    except ImportError:
        try:
            from server.api_crm_advanced import crm_bp
            blueprints.append(("CRM Legacy", crm_bp))
        except ImportError as e:
            app.logger.error("No CRM API available: %s", e)
    
    try:
        from server.api_timeline_improved import timeline_bp
        blueprints.append(("Timeline", timeline_bp))
    except ImportError:
        try:
            from server.api_timeline import timeline_bp
            blueprints.append(("Timeline Legacy", timeline_bp))
        except ImportError as e:
            app.logger.error("No Timeline API available: %s", e)
    
    try:
        from server.api_business import biz_bp
        blueprints.append(("Business Management", biz_bp))
    except ImportError as e:
        app.logger.error("No Business API available: %s", e)
    
    try:
        from server.api_whatsapp_improved import whatsapp_bp
        blueprints.append(("WhatsApp", whatsapp_bp))
    except ImportError:
        try:
            from server.whatsapp_api import whatsapp_api_bp
            blueprints.append(("WhatsApp Legacy", whatsapp_api_bp))
        except ImportError as e:
            app.logger.error("No WhatsApp API available: %s", e)
    
    # Register all successful blueprints
    registered = 0
    failed = 0
    
    for name, bp in blueprints:
        try:
            app.register_blueprint(bp)
            app.logger.info("✅ %s registered successfully", name)
            registered += 1
        except Exception as e:
            app.logger.error("❌ %s registration failed: %s", name, e)
            failed += 1
    
    app.logger.info("🎯 Blueprint registration complete: %d success, %d failed", registered, failed)
    return registered, failed