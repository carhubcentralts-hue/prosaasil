"""
AgentLocator v39 - Centralized Blueprint Registration
רישום Blueprint מרוכז לחיבור כל ה־APIs בצורה מסודרת
"""

def register_blueprints(app):
    """Register all application blueprints in centralized location"""
    
    # Core CRM and communication blueprints
    try:
        from ..api_crm_advanced import crm_bp
        app.register_blueprint(crm_bp)
        app.logger.info("✅ Advanced CRM Blueprint registered")
    except ImportError as e:
        app.logger.warning(f"⚠️ CRM Blueprint not found: {e}")
    
    try:
        from ..api_whatsapp_advanced import whatsapp_bp  
        app.register_blueprint(whatsapp_bp)
        app.logger.info("✅ Advanced WhatsApp Blueprint registered")
    except ImportError as e:
        app.logger.warning(f"⚠️ WhatsApp Blueprint not found: {e}")
    
    # Task and notification management
    try:
        from ..api_tasks import tasks_bp
        app.register_blueprint(tasks_bp)
        app.logger.info("✅ Tasks Blueprint registered")
    except ImportError as e:
        app.logger.warning(f"⚠️ Tasks Blueprint not found: {e}")
        
    try:
        from ..api_notifications import notifications_bp
        app.register_blueprint(notifications_bp)
        app.logger.info("✅ Notifications Blueprint registered")
    except ImportError as e:
        app.logger.warning(f"⚠️ Notifications Blueprint not found: {e}")
    
    # Business operations
    try:
        from ..api_contracts import contracts_bp
        app.register_blueprint(contracts_bp)
        app.logger.info("✅ Contracts Blueprint registered")
    except ImportError as e:
        app.logger.warning(f"⚠️ Contracts Blueprint not found: {e}")
        
    try:
        from ..api_invoices import invoices_bp
        app.register_blueprint(invoices_bp)
        app.logger.info("✅ Invoices Blueprint registered")
    except ImportError as e:
        app.logger.warning(f"⚠️ Invoices Blueprint not found: {e}")
        
    try:
        from ..api_signatures import signatures_bp
        app.register_blueprint(signatures_bp)
        app.logger.info("✅ Signatures Blueprint registered")
    except ImportError as e:
        app.logger.warning(f"⚠️ Signatures Blueprint not found: {e}")
    
    # Analytics and reporting
    try:
        from ..api_stats import stats_bp
        app.register_blueprint(stats_bp)
        app.logger.info("✅ Stats Blueprint registered")
    except ImportError as e:
        app.logger.warning(f"⚠️ Stats Blueprint not found: {e}")
    
    # Timeline API (will be created)
    try:
        from ..api_timeline import timeline_bp
        app.register_blueprint(timeline_bp)
        app.logger.info("✅ Timeline Blueprint registered")
    except ImportError as e:
        app.logger.warning(f"⚠️ Timeline Blueprint not found: {e}")
    
    # Core communication
    try:
        from ..routes_twilio import twilio_bp
        app.register_blueprint(twilio_bp)
        app.logger.info("✅ Twilio Blueprint registered")
    except ImportError as e:
        app.logger.warning(f"⚠️ Twilio Blueprint not found: {e}")
        
    app.logger.info("🎯 All blueprints registration completed")