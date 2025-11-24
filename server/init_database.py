#!/usr/bin/env python3
"""
Database Initialization for Production Deployments
Ensures the system is ready to use out-of-the-box
"""
import logging
import json
from datetime import datetime
from werkzeug.security import generate_password_hash
from server.db import db
from server.models_sql import User, Business, LeadStatus, FAQ, BusinessSettings

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
        print("🔧 Starting database initialization...")
        logger.info("🔧 Starting database initialization...")
        
        # 1. Ensure at least one business exists
        business = Business.query.first()
        if not business:
            print("📊 No business found, creating default business...")
            logger.info("📊 No business found, creating default business...")
            business = Business(
                name="עסק ראשי",
                business_type="real_estate",
                phone_e164="+972500000000",  # Default placeholder phone
                whatsapp_number="+972500000000",  # Default WhatsApp number
                greeting_message="שלום! איך אפשר לעזור?",  # Default greeting
                whatsapp_greeting="שלום! איך אפשר לעזור?",  # Default WhatsApp greeting
                system_prompt="אתה עוזר נדל\"ן מקצועי ב{{business_name}}. תפקידך לעזור ללקוחות למצוא נכסים.",  # ✅ עם placeholder!
                voice_message="שלום מ{{business_name}}",  # ✅ עם placeholder!
                is_active=True,
                calls_enabled=True,
                crm_enabled=True,
                whatsapp_enabled=True,
                phone_permissions=True,
                whatsapp_permissions=True,
                payments_enabled=False,
                default_provider="paypal",
                working_hours="08:00-18:00",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(business)
            db.session.commit()
            print(f"✅ Created default business: {business.name} (ID: {business.id})")
            logger.info(f"✅ Created default business: {business.name} (ID: {business.id})")
        else:
            print(f"✅ Business exists: {business.name} (ID: {business.id})")
            logger.info(f"✅ Business exists: {business.name} (ID: {business.id})")
        
        # 2. Ensure admin user exists
        admin = User.query.filter_by(email='admin@admin.com').first()
        if not admin:
            print("👤 No admin user found, creating admin...")
            logger.info("👤 No admin user found, creating admin...")
            # Password: admin123
            password_hash = generate_password_hash('admin123', method='scrypt')
            admin = User(
                email='admin@admin.com',
                password_hash=password_hash,
                name='Admin User',
                role='superadmin',
                business_id=None,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.session.add(admin)
            db.session.commit()
            print(f"✅ Created admin user: admin@admin.com (ID: {admin.id})")
            logger.info(f"✅ Created admin user: admin@admin.com (ID: {admin.id})")
        else:
            print(f"✅ Admin user exists: {admin.email} (ID: {admin.id})")
            logger.info(f"✅ Admin user exists: {admin.email} (ID: {admin.id})")
            
            # 3. Ensure admin is superadmin with no business_id
            if admin.role != 'superadmin':
                print("🔧 Updating admin to superadmin...")
                admin.role = 'superadmin'
                db.session.commit()
            if admin.business_id is not None:
                print("🔧 Removing admin business_id...")
                admin.business_id = None
                db.session.commit()
        
        # 4. Ensure default lead statuses exist for this business
        existing_statuses = LeadStatus.query.filter_by(business_id=business.id).count()
        if existing_statuses == 0:
            print("📋 No lead statuses found, creating defaults...")
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
            print(f"✅ Created {len(default_statuses)} default lead statuses")
            logger.info(f"✅ Created {len(default_statuses)} default lead statuses")
        else:
            print(f"✅ Lead statuses exist: {existing_statuses} statuses found")
            logger.info(f"✅ Lead statuses exist: {existing_statuses} statuses found")
        
        # 5. 🔒 BUILD 120 FIX: NEVER auto-create FAQs! User creates them via UI
        # Previous approach was broken - FAQs were deleted on every deployment
        # because init_database ran BEFORE migrations created the table
        try:
            total_faqs = FAQ.query.count()  # Check ALL FAQs (not just this business)
            print(f"✅ FAQs table exists: {total_faqs} FAQs found across all businesses")
            logger.info(f"✅ FAQs: {total_faqs} total (user creates FAQs via UI)")
        except Exception as e:
            # FAQs table doesn't exist yet (migrations haven't run)
            print(f"⚠️ FAQs table not ready: {e}")
            print("   (This is normal on first deployment - table will be created by migrations)")
            logger.warning(f"FAQs table not ready: {e}")
        
        # 6. Ensure BusinessSettings exists for this business
        # CRITICAL FIX BUILD 111: Settings (slot_size, 24/7, etc.) must persist across deployments!
        existing_settings = BusinessSettings.query.filter_by(tenant_id=business.id).first()
        if not existing_settings:
            print("⚙️ No business_settings found, creating default settings...")
            logger.info("⚙️ No business_settings found, creating default settings...")
            
            # Create default BusinessSettings
            settings = BusinessSettings(
                tenant_id=business.id,
                slot_size_min=60,  # Default: 60 minutes
                allow_24_7=False,  # Default: business hours only
                booking_window_days=30,  # Default: 30 days ahead
                min_notice_min=0,  # Default: no minimum notice
                ai_prompt=json.dumps({
                    "calls": "אתה עוזר AI למכירות נדל\"ן. שמור על שיחה קצרה וממוקדת.",
                    "whatsapp": "אתה עוזר AI למכירות נדל\"ן ב-WhatsApp. היה ידידותי ומקצועי."
                }),
                working_hours="09:00-18:00",
                voice_message=None
            )
            db.session.add(settings)
            db.session.commit()
            
            print(f"✅ Created default business_settings (slot_size: 60min, 24/7: False)")
            logger.info(f"✅ Created default business_settings")
        else:
            print(f"✅ Business settings exist (slot_size: {existing_settings.slot_size_min}min, 24/7: {existing_settings.allow_24_7})")
            logger.info(f"✅ Business settings exist (slot_size: {existing_settings.slot_size_min}min)")
        
        print("✅ Database initialization completed successfully!")
        print(f"📧 Admin login: admin@admin.com / admin123")
        print(f"🏢 Business ID: {business.id}")
        logger.info("✅ Database initialization completed successfully!")
        logger.info(f"📧 Admin login: admin@admin.com / admin123")
        logger.info(f"🏢 Business ID: {business.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        print(traceback.format_exc())
        logger.error(f"❌ Database initialization failed: {e}")
        logger.error(traceback.format_exc())
        db.session.rollback()
        return False
