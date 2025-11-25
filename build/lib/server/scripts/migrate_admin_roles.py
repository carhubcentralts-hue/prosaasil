#!/usr/bin/env python3
"""
Migration Script: Update legacy admin/manager roles to system_admin
This script runs during deployment to update old role names to the new structure
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from server.app_factory import create_app
from server.db import db
from server.models_sql import User

def migrate_admin_roles():
    """
    Update legacy role names to new 4-tier structure:
    - 'admin'/'manager' with business_id=NULL -> 'system_admin' (global admin)
    - 'manager' with business_id!=NULL -> 'owner' (business owner)
    - 'admin' with business_id!=NULL -> 'admin' (business admin - no change)
    - 'superadmin' -> 'system_admin' (always global)
    - 'business' -> 'admin' (business admin)
    
    This ensures backward compatibility with production databases
    """
    print("🔄 Starting admin roles migration...")
    
    # Find all users with legacy roles
    legacy_roles = ['admin', 'superadmin', 'manager', 'business']
    users_to_update = User.query.filter(User.role.in_(legacy_roles)).all()
    
    if not users_to_update:
        print("✅ No legacy roles found - all users already migrated!")
        return
    
    print(f"📊 Found {len(users_to_update)} users with legacy roles")
    
    for user in users_to_update:
        old_role = user.role
        new_role = old_role  # Default to current role
        
        # Determine new role based on legacy role AND business_id
        if old_role in ['admin', 'superadmin']:
            if user.business_id is None:
                # Global admin without business -> system_admin
                new_role = 'system_admin'
                print(f"📝 Global admin: '{user.email}' (ID={user.id}): {old_role} -> {new_role} (no business)")
            else:
                # Admin tied to specific business -> keep as admin
                new_role = 'admin'
                print(f"📝 Business admin: '{user.email}' (ID={user.id}): {old_role} -> {new_role} (business_id={user.business_id})")
        
        elif old_role == 'manager':
            if user.business_id is None:
                # Global manager without business -> system_admin
                new_role = 'system_admin'
                print(f"📝 Global manager: '{user.email}' (ID={user.id}): {old_role} -> {new_role} (no business)")
            else:
                # Manager tied to specific business -> owner
                new_role = 'owner'
                print(f"📝 Business owner: '{user.email}' (ID={user.id}): {old_role} -> {new_role} (business_id={user.business_id})")
        
        elif old_role == 'business':
            # Business role -> admin
            new_role = 'admin'
            print(f"📝 Business user: '{user.email}' (ID={user.id}): {old_role} -> {new_role}")
        
        user.role = new_role
    
    db.session.commit()
    print(f"\n✅ Successfully migrated {len(users_to_update)} users to new role structure!")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        try:
            migrate_admin_roles()
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
