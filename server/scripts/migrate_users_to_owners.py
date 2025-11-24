#!/usr/bin/env python3
"""
Migration Script: Ensure every Business has at least one owner User
This script runs as part of deployment to create owner users for existing businesses
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from server.app_factory import create_app
from server.db import db
from server.models_sql import Business, User
from werkzeug.security import generate_password_hash

def migrate_users_to_owners():
    """
    Ensure every business has at least one owner user
    - For businesses with users but no owner: promote first user to owner
    - For businesses without users: SKIP (admin must manually create owner via UI)
    
    SECURITY: Never auto-create placeholder users with static passwords
    """
    print("🔄 Starting User-to-Owner migration...")
    
    businesses = Business.query.all()
    print(f"📊 Found {len(businesses)} businesses")
    
    businesses_without_owner = []
    
    for biz in businesses:
        # Check if business already has an owner
        existing_owner = User.query.filter_by(business_id=biz.id, role="owner").first()
        
        if existing_owner:
            print(f"✅ Business '{biz.name}' (ID={biz.id}) already has owner: {existing_owner.email}")
            continue
        
        # Check if business has any users
        existing_users = User.query.filter_by(business_id=biz.id).all()
        
        if existing_users:
            # Promote first user to owner
            first_user = existing_users[0]
            print(f"📝 Promoting user '{first_user.email}' to owner for business '{biz.name}' (ID={biz.id})")
            first_user.role = "owner"
            db.session.commit()
            print(f"✅ User promoted to owner")
        else:
            # ❌ SECURITY: NO auto-creation of placeholder users
            print(f"⚠️  Business '{biz.name}' (ID={biz.id}) has NO users")
            print(f"   → Admin must create owner via UI: /app/admin/businesses")
            businesses_without_owner.append(biz)
    
    print("\n✅ User-to-Owner migration completed!")
    
    if businesses_without_owner:
        print(f"\n⚠️  {len(businesses_without_owner)} businesses need manual owner creation:")
        for biz in businesses_without_owner:
            print(f"   - {biz.name} (ID={biz.id})")
        print("\n   → Login as system_admin and use BusinessUsersModal to create owners")
    else:
        print("\n✅ All businesses have owners!")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        try:
            migrate_users_to_owners()
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
