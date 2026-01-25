#!/usr/bin/env python3
"""
Static validation test for push_enabled migration and transaction hardening.

This test verifies:
1. db_migrate.py contains migration for users.push_enabled
2. Migration uses correct column type and default value
3. init_database.py has rollback calls after database exceptions
4. auth_api.py has rollback calls after database exceptions
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_push_enabled_migration():
    """Verify push_enabled migration exists in db_migrate.py"""
    print("\n=== Checking push_enabled Migration ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Check 1: Migration 57c comment exists
        if 'Migration 57c' in content and 'push_enabled' in content:
            print("✅ Migration 57c for push_enabled found")
        else:
            print("❌ Migration 57c comment not found")
            all_ok = False
        
        # Check 2: Column check exists
        if "check_column_exists('users', 'push_enabled')" in content:
            print("✅ Column existence check found")
        else:
            print("❌ Column existence check not found")
            all_ok = False
        
        # Check 3: ALTER TABLE statement exists
        if 'ALTER TABLE users' in content and 'ADD COLUMN push_enabled' in content:
            print("✅ ALTER TABLE statement found")
        else:
            print("❌ ALTER TABLE statement not found")
            all_ok = False
        
        # Check 4: Correct data type (BOOLEAN)
        if 'push_enabled BOOLEAN' in content:
            print("✅ Correct data type (BOOLEAN) specified")
        else:
            print("❌ Incorrect or missing data type")
            all_ok = False
        
        # Check 5: NOT NULL constraint
        if 'push_enabled BOOLEAN NOT NULL' in content:
            print("✅ NOT NULL constraint specified")
        else:
            print("❌ NOT NULL constraint missing")
            all_ok = False
        
        # Check 6: DEFAULT TRUE
        if 'DEFAULT TRUE' in content or 'DEFAULT true' in content:
            print("✅ DEFAULT TRUE specified")
        else:
            print("❌ DEFAULT TRUE missing")
            all_ok = False
        
        # Check 7: Migration marker
        if "migrations_applied.append('add_users_push_enabled')" in content:
            print("✅ Migration marker found")
        else:
            print("❌ Migration marker not found")
            all_ok = False
        
        return all_ok
    
    except Exception as e:
        print(f"❌ Error checking file: {e}")
        return False

def check_init_database_rollbacks():
    """Verify init_database.py has proper rollback handling"""
    print("\n=== Checking init_database.py Rollbacks ===")
    
    filepath = 'server/init_database.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Check for rollback after User.query exceptions
        user_query_pattern = r'User\.query.*?except.*?db\.session\.rollback\(\)'
        if re.search(user_query_pattern, content, re.DOTALL):
            print("✅ User.query has rollback handling")
        else:
            print("❌ User.query missing rollback handling")
            all_ok = False
        
        # Check for rollback after Business.query exceptions
        business_query_pattern = r'Business\.query.*?except.*?db\.session\.rollback\(\)'
        if re.search(business_query_pattern, content, re.DOTALL):
            print("✅ Business.query has rollback handling")
        else:
            print("❌ Business.query missing rollback handling")
            all_ok = False
        
        # Check for rollback after LeadStatus.query exceptions
        if 'LeadStatus.query' in content:
            leadstatus_query_pattern = r'LeadStatus\.query.*?except.*?db\.session\.rollback\(\)'
            if re.search(leadstatus_query_pattern, content, re.DOTALL):
                print("✅ LeadStatus.query has rollback handling")
            else:
                print("❌ LeadStatus.query missing rollback handling")
                all_ok = False
        
        # Check for rollback after FAQ.query exceptions
        if 'FAQ.query' in content:
            faq_query_pattern = r'FAQ\.query.*?except.*?db\.session\.rollback\(\)'
            if re.search(faq_query_pattern, content, re.DOTALL):
                print("✅ FAQ.query has rollback handling")
            else:
                print("❌ FAQ.query missing rollback handling")
                all_ok = False
        
        # Check for rollback after BusinessSettings.query exceptions
        if 'BusinessSettings.query' in content:
            settings_query_pattern = r'BusinessSettings\.query.*?except.*?db\.session\.rollback\(\)'
            if re.search(settings_query_pattern, content, re.DOTALL):
                print("✅ BusinessSettings.query has rollback handling")
            else:
                print("❌ BusinessSettings.query missing rollback handling")
                all_ok = False
        
        # Check for general exception rollback at the end
        if 'db.session.rollback()' in content and 'except Exception as e:' in content:
            print("✅ General exception rollback found")
        else:
            print("❌ General exception rollback missing")
            all_ok = False
        
        return all_ok
    
    except Exception as e:
        print(f"❌ Error checking file: {e}")
        return False

def check_auth_api_rollbacks():
    """Verify auth_api.py already has proper rollback handling"""
    print("\n=== Checking auth_api.py Rollbacks ===")
    
    filepath = 'server/auth_api.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Check for rollback in login endpoint
        if 'def login()' in content:
            login_section = content[content.find('def login()'):]
            if 'db.session.rollback()' in login_section[:5000]:
                print("✅ login() has rollback handling")
            else:
                print("❌ login() missing rollback handling")
                all_ok = False
        
        # Check for rollback in refresh_token endpoint
        if 'def refresh_token()' in content:
            refresh_section = content[content.find('def refresh_token()'):]
            if 'db.session.rollback()' in refresh_section[:5000]:
                print("✅ refresh_token() has rollback handling")
            else:
                print("❌ refresh_token() missing rollback handling")
                all_ok = False
        
        # Check for rollback in get_current_user endpoint
        if 'def get_current_user()' in content:
            current_section = content[content.find('def get_current_user()'):]
            if 'db.session.rollback()' in current_section[:3000]:
                print("✅ get_current_user() has rollback handling")
            else:
                print("❌ get_current_user() missing rollback handling")
                all_ok = False
        
        return all_ok
    
    except Exception as e:
        print(f"❌ Error checking file: {e}")
        return False

def check_environment_validation():
    """Verify environment_validation.py includes push_enabled"""
    print("\n=== Checking environment_validation.py ===")
    
    filepath = 'server/environment_validation.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Check 1: CRITICAL_COLUMNS dictionary exists
        if 'CRITICAL_COLUMNS' in content:
            print("✅ CRITICAL_COLUMNS dictionary found")
        else:
            print("❌ CRITICAL_COLUMNS dictionary not found")
            all_ok = False
        
        # Check 2: users table section exists
        if "'users':" in content or '"users":' in content:
            print("✅ users table section found in CRITICAL_COLUMNS")
        else:
            print("❌ users table section not found in CRITICAL_COLUMNS")
            all_ok = False
        
        # Check 3: push_enabled in users table
        # Simple check: both 'users' and 'push_enabled' should be in the file
        # and push_enabled should appear near users in CRITICAL_COLUMNS section
        if "'push_enabled'" in content or '"push_enabled"' in content:
            # Find CRITICAL_COLUMNS section
            critical_start = content.find('CRITICAL_COLUMNS')
            if critical_start != -1:
                # Get the section from CRITICAL_COLUMNS to next major section or end
                # Look for 500 chars after users section starts
                users_start = content.find("'users':", critical_start)
                if users_start == -1:
                    users_start = content.find('"users":', critical_start)
                
                if users_start != -1:
                    # Check within 500 chars of users section start
                    users_section = content[users_start:users_start+500]
                    
                    if 'push_enabled' in users_section:
                        print("✅ push_enabled found in users CRITICAL_COLUMNS")
                    else:
                        print("❌ push_enabled not in users section")
                        all_ok = False
                else:
                    print("❌ Could not find users section")
                    all_ok = False
            else:
                print("❌ Could not find CRITICAL_COLUMNS section")
                all_ok = False
        else:
            print("❌ push_enabled not found in file")
            all_ok = False
        
        return all_ok
    
    except Exception as e:
        print(f"❌ Error checking file: {e}")
        return False

def main():
    """Run all validation checks"""
    print("=" * 70)
    print("Static Validation: push_enabled Migration & Transaction Hardening")
    print("=" * 70)
    
    results = []
    
    # Check 1: push_enabled migration
    results.append(("push_enabled Migration", check_push_enabled_migration()))
    
    # Check 2: init_database rollbacks
    results.append(("init_database Rollbacks", check_init_database_rollbacks()))
    
    # Check 3: auth_api rollbacks
    results.append(("auth_api Rollbacks", check_auth_api_rollbacks()))
    
    # Check 4: environment_validation
    results.append(("environment_validation", check_environment_validation()))
    
    # Print summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n✅ All validation checks passed!")
        return 0
    else:
        print("\n❌ Some validation checks failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
