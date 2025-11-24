#!/usr/bin/env python3
"""
Database Seed Script - Ensures baseline data exists in all environments
This script is IDEMPOTENT - safe to run multiple times
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.models_sql import db, User, Business
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError

def seed_system_admin():
    """
    Ensures global system_admin exists
    Email: admin@admin.com
    Password: admin123
    """
    admin_email = "admin@admin.com"
    admin_password = "admin123"
    
    # Check if system admin exists
    admin = User.query.filter_by(email=admin_email).first()
    
    if admin:
        # Update existing admin to ensure correct settings
        print(f"✅ Found existing system_admin: {admin_email}")
        admin.business_id = None  # Ensure global
        admin.role = 'system_admin'
        admin.is_active = True
        print(f"   Updated to: business_id=NULL, role=system_admin")
    else:
        # Create new system admin
        print(f"🆕 Creating system_admin: {admin_email}")
        admin = User(
            email=admin_email,
            password_hash=generate_password_hash(admin_password, method='scrypt'),
            name="System Administrator",
            role='system_admin',
            business_id=None,  # Global admin
            is_active=True
        )
        db.session.add(admin)
    
    try:
        db.session.commit()
        print(f"✅ System admin ready: {admin_email} (business_id=NULL)")
        return admin
    except IntegrityError as e:
        db.session.rollback()
        print(f"❌ Error creating system admin: {e}")
        return None

def seed_demo_business():
    """
    Ensures at least one demo business exists for testing
    """
    business_name = "שי דירות ומשרדים בע״מ"
    
    # Check if demo business exists
    business = Business.query.filter_by(name=business_name).first()
    
    if business:
        print(f"✅ Found existing business: {business_name} (id={business.id})")
        return business
    else:
        print(f"🆕 Creating demo business: {business_name}")
        business = Business(
            name=business_name,
            business_type='נדלן ותיווך',
            is_active=True
        )
        db.session.add(business)
        
        try:
            db.session.commit()
            print(f"✅ Demo business created: {business_name} (id={business.id})")
            return business
        except IntegrityError as e:
            db.session.rollback()
            print(f"❌ Error creating business: {e}")
            return None

def main():
    """Main seed function"""
    print("=" * 50)
    print("🌱 Starting Database Seed...")
    print("=" * 50)
    
    # Import app factory to get db context
    from server.app_factory import create_app
    
    app = create_app()
    
    with app.app_context():
        # Seed system admin
        admin = seed_system_admin()
        
        # Seed demo business
        business = seed_demo_business()
        
        print("=" * 50)
        if admin:
            print("✅ Seed completed successfully!")
            print(f"   System Admin: {admin.email} (business_id={admin.business_id})")
        else:
            print("⚠️  Seed completed with warnings")
        print("=" * 50)

if __name__ == "__main__":
    main()
