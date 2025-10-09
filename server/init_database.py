#!/usr/bin/env python3
"""
Database Initialization for Production Deployments
Ensures the system is ready to use out-of-the-box
"""
import logging
from datetime import datetime
from werkzeug.security import generate_password_hash
from server.db import db
from server.models_sql import User, Business, LeadStatus

logger = logging.getLogger(__name__)

def initialize_production_database():
    """
    Initialize production database with essential data
    - Creates default business if none exists
    - Creates admin user if none exists
    - Links admin to business
    - Creates default lead statuses
    
    This runs automatically on app startup and is idempotent (safe to run multiple times)
    """
    try:
        logger.info("🔧 Starting database initialization...")
        
        # 1. Ensure at least one business exists
        business = Business.query.first()
        if not business:
            logger.info("📊 No business found, creating default business...")
            business = Business(
                name="עסק ראשי",
                business_type="real_estate",
                is_active=True,
                calls_enabled=True,
                crm_enabled=True,
                whatsapp_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(business)
            db.session.commit()
            logger.info(f"✅ Created default business: {business.name} (ID: {business.id})")
        else:
            logger.info(f"✅ Business exists: {business.name} (ID: {business.id})")
        
        # 2. Ensure admin user exists
        admin = User.query.filter_by(email='admin@admin.com').first()
        if not admin:
            logger.info("👤 No admin user found, creating admin...")
            # Password: admin123
            password_hash = generate_password_hash('admin123', method='scrypt')
            admin = User(
                email='admin@admin.com',
                password_hash=password_hash,
                name='Admin User',
                role='admin',
                business_id=business.id,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.session.add(admin)
            db.session.commit()
            logger.info(f"✅ Created admin user: admin@admin.com (ID: {admin.id})")
        else:
            logger.info(f"✅ Admin user exists: {admin.email} (ID: {admin.id})")
            
            # 3. Ensure admin has business_id
            if not admin.business_id:
                logger.info("🔗 Linking admin to business...")
                admin.business_id = business.id
                db.session.commit()
                logger.info(f"✅ Admin linked to business ID: {business.id}")
        
        # 4. Ensure default lead statuses exist for this business
        existing_statuses = LeadStatus.query.filter_by(business_id=business.id).count()
        if existing_statuses == 0:
            logger.info("📋 No lead statuses found, creating defaults...")
            default_statuses = [
                {'name': 'new', 'label': 'חדש', 'color': '#3b82f6', 'order_index': 0, 'is_default': True},
                {'name': 'attempting', 'label': 'בניסיון יצירת קשר', 'color': '#f59e0b', 'order_index': 1},
                {'name': 'contacted', 'label': 'יצר קשר', 'color': '#8b5cf6', 'order_index': 2},
                {'name': 'qualified', 'label': 'מתאים', 'color': '#10b981', 'order_index': 3},
                {'name': 'won', 'label': 'נסגר בהצלחה', 'color': '#059669', 'order_index': 4},
                {'name': 'lost', 'label': 'לא רלוונטי', 'color': '#ef4444', 'order_index': 5},
                {'name': 'unqualified', 'label': 'לא מתאים', 'color': '#6b7280', 'order_index': 6}
            ]
            
            for status_data in default_statuses:
                status = LeadStatus(
                    business_id=business.id,
                    name=status_data['name'],
                    label=status_data['label'],
                    color=status_data['color'],
                    order_index=status_data['order_index'],
                    is_default=status_data.get('is_default', False),
                    is_system=True,
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(status)
            
            db.session.commit()
            logger.info(f"✅ Created {len(default_statuses)} default lead statuses")
        else:
            logger.info(f"✅ Lead statuses exist: {existing_statuses} statuses found")
        
        logger.info("✅ Database initialization completed successfully!")
        logger.info(f"📧 Admin login: admin@admin.com / admin123")
        logger.info(f"🏢 Business ID: {business.id}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        db.session.rollback()
        return False
