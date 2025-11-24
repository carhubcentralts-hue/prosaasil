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
    Update legacy role names to new structure:
    - 'admin' -> 'system_admin'
    - 'manager' -> 'system_admin'
    - 'superadmin' -> 'system_admin'
    
    This ensures backward compatibility with production databases
    """
    print("🔄 Starting admin roles migration...")
    
    # Find all users with legacy roles
    legacy_roles = ['admin', 'manager', 'superadmin']
    users_to_update = User.query.filter(User.role.in_(legacy_roles)).all()
    
    if not users_to_update:
        print("✅ No legacy roles found - all users already migrated!")
        return
    
    print(f"📊 Found {len(users_to_update)} users with legacy roles")
    
    for user in users_to_update:
        old_role = user.role
        user.role = 'system_admin'
        print(f"📝 Updating user '{user.email}' (ID={user.id}): {old_role} -> system_admin")
    
    db.session.commit()
    print(f"\n✅ Successfully updated {len(users_to_update)} users to system_admin role!")

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
