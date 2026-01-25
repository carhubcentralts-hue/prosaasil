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
    - Creates system business for global admin
    - Creates default business if none exists
    - Creates admin user if none exists
    - Links admin to system business
    - Creates default lead statuses
    
    This runs automatically on app startup and is idempotent (safe to run multiple times)
    """
    try:
        logger.info("🔧 Starting database initialization...")
        logger.info("🔧 Starting database initialization...")
        
        # 0. Ensure System business exists for system_admin (FIX for business_id NOT NULL)
        try:
            system_business = Business.query.filter_by(name="System").first()
        except Exception as db_error:
            # 🔥 CRITICAL FIX: Rollback transaction to prevent "InFailedSqlTransaction"
            db.session.rollback()
            logger.error(f"[INIT_DB] Database error querying System business: {db_error}")
            raise
        
        if not system_business:
            logger.info("🏢 Creating System business for global admin...")
            logger.info("🏢 Creating System business for global admin...")
            system_business = Business(
                name="System",
                business_type="system",
                phone_e164="+972000000000",
                whatsapp_number="+972000000000",
                greeting_message="System",
                whatsapp_greeting="System",
                system_prompt="System business for administrative purposes",
                voice_message="System",
                is_active=True,
                calls_enabled=False,
                crm_enabled=False,
                whatsapp_enabled=False,
                phone_permissions=False,
                whatsapp_permissions=False,
                payments_enabled=False,
                default_provider="paypal",
                working_hours="24/7",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(system_business)
            db.session.commit()
            logger.info(f"✅ Created System business (ID: {system_business.id})")
            logger.info(f"✅ Created System business (ID: {system_business.id})")
        else:
            logger.info(f"✅ System business exists (ID: {system_business.id})")
            logger.info(f"✅ System business exists (ID: {system_business.id})")
        
        # 1. Ensure at least one regular business exists
        try:
            business = Business.query.filter(Business.name != "System").first()
        except Exception as db_error:
            # 🔥 CRITICAL FIX: Rollback transaction to prevent "InFailedSqlTransaction"
            db.session.rollback()
            logger.error(f"[INIT_DB] Database error querying regular business: {db_error}")
            raise
        
        if not business:
            logger.info("📊 No regular business found, creating default business...")
            logger.info("📊 No regular business found, creating default business...")
            business = Business(
                name="עסק ראשי",
                business_type="general",  # 🔥 BUILD 200: Generic default
                phone_e164="+972500000000",  # Default placeholder phone
                whatsapp_number="+972500000000",  # Default WhatsApp number
                greeting_message="שלום! איך אפשר לעזור?",  # Default greeting
                whatsapp_greeting="שלום! איך אפשר לעזור?",  # Default WhatsApp greeting
                system_prompt="אתה נציג שירות מקצועי ב{{business_name}}. עזור ללקוחות בצורה אדיבה ומקצועית.",  # ✅ כללי - לא מניח סוג עסק!
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
            logger.info(f"✅ Created default business: {business.name} (ID: {business.id})")
            logger.info(f"✅ Created default business: {business.name} (ID: {business.id})")
        else:
            logger.info(f"✅ Regular business exists: {business.name} (ID: {business.id})")
            logger.info(f"✅ Regular business exists: {business.name} (ID: {business.id})")
        
        # 2. Ensure system admin user exists (FIXED: must have business_id)
        try:
            admin = User.query.filter_by(email='admin@admin.com').first()
        except Exception as db_error:
            # 🔥 CRITICAL FIX: Rollback transaction to prevent "InFailedSqlTransaction"
            db.session.rollback()
            logger.error(f"[INIT_DB] Database error querying admin user: {db_error}")
            raise
        
        if not admin:
            logger.info("👤 No system admin user found, creating system_admin...")
            logger.info("👤 No system admin user found, creating system_admin...")
            # Password: admin123
            password_hash = generate_password_hash('admin123', method='scrypt')
            admin = User(
                email='admin@admin.com',
                password_hash=password_hash,
                name='System Administrator',
                role='system_admin',
                business_id=system_business.id,  # ✅ FIXED: Link to System business (not None)
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.session.add(admin)
            db.session.commit()
            logger.info(f"✅ Created system admin user: admin@admin.com (ID: {admin.id}, business_id: {admin.business_id})")
            logger.info(f"✅ Created system admin user: admin@admin.com (ID: {admin.id}, business_id: {admin.business_id})")
        else:
            logger.info(f"✅ System admin user exists: {admin.email} (ID: {admin.id}, role: {admin.role}, business_id: {admin.business_id})")
            logger.info(f"✅ System admin user exists: {admin.email} (ID: {admin.id}, role: {admin.role}, business_id: {admin.business_id})")
            
            # ✅ Ensure system_admin is linked to System business
            updates_needed = False
            
            # Link to System business if not already
            if admin.role == 'system_admin' and admin.business_id != system_business.id:
                logger.info(f"🔗 Linking system_admin to System business (ID: {system_business.id})...")
                logger.info(f"🔗 Linking system_admin to System business (ID: {system_business.id})...")
                admin.business_id = system_business.id
                updates_needed = True
            
            # ✅ ONLY upgrade admin@admin.com role, not other admins!
            if admin.role in ['admin', 'manager']:
                logger.info(f"📝 Upgrading admin@admin.com role from '{admin.role}' to 'system_admin'...")
                logger.info(f"📝 Upgrading admin@admin.com role from '{admin.role}' to 'system_admin'...")
                admin.role = 'system_admin'
                admin.business_id = system_business.id  # ✅ Link to System business
                updates_needed = True
            
            if updates_needed:
                db.session.commit()
                logger.info(f"✅ Admin (admin@admin.com) updated successfully")
                logger.info(f"✅ Admin (admin@admin.com) updated successfully")
        
        # ✅ Print all users for debugging
        try:
            all_users = User.query.all()
        except Exception as db_error:
            # 🔥 CRITICAL FIX: Rollback transaction to prevent "InFailedSqlTransaction"
            db.session.rollback()
            logger.error(f"[INIT_DB] Database error querying all users: {db_error}")
            raise
        
        logger.info(f"\n📊 Total users in database: {len(all_users)}")
        logger.info(f"📊 Total users in database: {len(all_users)}")
        for u in all_users:
            logger.info(f"  - User {u.id}: {u.email} | role={u.role} | business_id={u.business_id}")
            logger.info(f"  - User {u.id}: {u.email} | role={u.role} | business_id={u.business_id}")
        
        # 4. Ensure default lead statuses exist for the regular business (not System)
        try:
            existing_statuses = LeadStatus.query.filter_by(business_id=business.id).count()
        except Exception as db_error:
            # 🔥 CRITICAL FIX: Rollback transaction to prevent "InFailedSqlTransaction"
            db.session.rollback()
            logger.error(f"[INIT_DB] Database error querying lead statuses: {db_error}")
            raise
        
        if existing_statuses == 0:
            logger.info("📋 No lead statuses found, creating defaults...")
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
            logger.info(f"✅ Created {len(default_statuses)} default lead statuses")
        else:
            logger.info(f"✅ Lead statuses exist: {existing_statuses} statuses found")
            logger.info(f"✅ Lead statuses exist: {existing_statuses} statuses found")
        
        # 5. 🔒 BUILD 120 FIX: NEVER auto-create FAQs! User creates them via UI
        # Previous approach was broken - FAQs were deleted on every deployment
        # because init_database ran BEFORE migrations created the table
        try:
            total_faqs = FAQ.query.count()  # Check ALL FAQs (not just this business)
            logger.info(f"✅ FAQs table exists: {total_faqs} FAQs found across all businesses")
            logger.info(f"✅ FAQs: {total_faqs} total (user creates FAQs via UI)")
        except Exception as e:
            # FAQs table doesn't exist yet (migrations haven't run)
            # 🔥 CRITICAL FIX: Rollback transaction to prevent "InFailedSqlTransaction"
            db.session.rollback()
            logger.warning(f"⚠️ FAQs table not ready: {e}")
            logger.info("   (This is normal on first deployment - table will be created by migrations)")
            logger.warning(f"FAQs table not ready: {e}")
        
        # 6. Ensure BusinessSettings exists for this business
        # CRITICAL FIX BUILD 111: Settings (slot_size, 24/7, etc.) must persist across deployments!
        try:
            existing_settings = BusinessSettings.query.filter_by(tenant_id=business.id).first()
        except Exception as db_error:
            # 🔥 CRITICAL FIX: Rollback transaction to prevent "InFailedSqlTransaction"
            db.session.rollback()
            logger.error(f"[INIT_DB] Database error querying business settings: {db_error}")
            raise
        
        if not existing_settings:
            logger.info("⚙️ No business_settings found, creating default settings...")
            logger.info("⚙️ No business_settings found, creating default settings...")
            
            # Create default BusinessSettings
            settings = BusinessSettings(
                tenant_id=business.id,
                slot_size_min=60,  # Default: 60 minutes
                allow_24_7=False,  # Default: business hours only
                booking_window_days=30,  # Default: 30 days ahead
                min_notice_min=0,  # Default: no minimum notice
                ai_prompt=json.dumps({
                    "calls": "אתה נציג שירות מקצועי ואדיב. שמור על שיחה קצרה וממוקדת. עזור ללקוח במה שהוא צריך.",
                    "whatsapp": "אתה נציג שירות מקצועי ב-WhatsApp. היה ידידותי ומקצועי. עזור ללקוח במה שהוא צריך."
                }),
                working_hours="09:00-18:00",
                voice_message=None
            )
            db.session.add(settings)
            db.session.commit()
            
            logger.info(f"✅ Created default business_settings (slot_size: 60min, 24/7: False)")
            logger.info(f"✅ Created default business_settings")
        else:
            logger.info(f"✅ Business settings exist (slot_size: {existing_settings.slot_size_min}min, 24/7: {existing_settings.allow_24_7})")
            logger.info(f"✅ Business settings exist (slot_size: {existing_settings.slot_size_min}min)")
        
        # 7. Ensure every business has at least one owner user (BUILD 124)
        logger.info("👥 Checking user ownership...")
        logger.info("👥 Checking user ownership...")
        
        # Run user-to-owner migration to ensure every business has an owner
        try:
            from server.scripts.migrate_users_to_owners import migrate_users_to_owners
            with db.session.no_autoflush:  # Prevent auto-flush during migration
                migrate_users_to_owners()
            logger.info("✅ User ownership check completed")
            logger.info("✅ User ownership check completed")
        except ImportError:
            # Migration script not available (dev environment)
            logger.warning("⚠️ User migration script not available - skipping")
            logger.warning("User migration script not available")
        except Exception as migration_error:
            logger.error(f"⚠️ User migration warning: {migration_error}")
            logger.warning(f"User migration warning: {migration_error}")
            # Don't fail initialization on migration errors
        
        logger.info("✅ Database initialization completed successfully!")
        logger.info(f"📧 Admin login: admin@admin.com / admin123")
        logger.info(f"🏢 Business ID: {business.id}")
        logger.info("✅ Database initialization completed successfully!")
        logger.info(f"📧 Admin login: admin@admin.com / admin123")
        logger.info(f"🏢 Business ID: {business.id}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        logger.error(f"❌ Database initialization failed: {e}")
        logger.error(traceback.format_exc())
        db.session.rollback()
        return False
