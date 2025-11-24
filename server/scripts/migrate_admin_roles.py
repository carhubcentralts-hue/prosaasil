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
    - 'admin' or 'superadmin' -> 'system_admin' (global admin)
    - 'manager' -> 'owner' (business owner)
    - 'business' -> 'admin' (business admin)
    
    This ensures backward compatibility with production databases
    """
    print("🔄 Starting admin roles migration...")
    
    # Role mapping: old_role -> new_role
    role_mapping = {
        'admin': 'system_admin',      # Global admins
        'superadmin': 'system_admin',  # Global admins
        'manager': 'owner',            # Business owners
        'business': 'admin',           # Business admins
    }
    
    # Find all users with legacy roles
    legacy_roles = list(role_mapping.keys())
    users_to_update = User.query.filter(User.role.in_(legacy_roles)).all()
    
    if not users_to_update:
        print("✅ No legacy roles found - all users already migrated!")
        return
    
    print(f"📊 Found {len(users_to_update)} users with legacy roles")
    
    for user in users_to_update:
        old_role = user.role
        new_role = role_mapping.get(old_role, old_role)  # Default to old role if not in mapping
        user.role = new_role
        print(f"📝 Updating user '{user.email}' (ID={user.id}): {old_role} -> {new_role}")
    
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
