#!/usr/bin/env python3
"""
Test Email Attachments Fix
Verifies that email_messages table has attachments column and email service saves them
"""

import os
import sys

def test_migration_79():
    """Test that Migration 79 added attachments column"""
    print("=" * 60)
    print("TEST: Migration 79 - Email Attachments Column")
    print("=" * 60)
    
    try:
        from server.db import db
        from server.app_factory import create_app
        from sqlalchemy import text
        
        app = create_app()
        with app.app_context():
            # Check if email_messages table exists
            result = db.session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'email_messages'
            """))
            
            if not result.fetchone():
                print("❌ email_messages table does not exist")
                print("   Run migrations first: python -m server.db_migrate")
                return False
            
            # Check if attachments column exists
            result = db.session.execute(text("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                  AND table_name = 'email_messages' 
                  AND column_name = 'attachments'
            """))
            
            col = result.fetchone()
            if not col:
                print("❌ attachments column does NOT exist in email_messages")
                print("   Migration 79 needs to be run")
                return False
            
            print(f"✅ attachments column exists")
            print(f"   Type: {col[1]}")
            print(f"   Default: {col[2]}")
            
            # Verify it's JSON type with default empty array
            if 'json' not in col[1].lower():
                print(f"⚠️  Column type is {col[1]}, expected JSON")
            
            return True
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_email_service_attachments():
    """Test that email service includes attachments in INSERT"""
    print("\n" + "=" * 60)
    print("TEST: Email Service Attachments Support")
    print("=" * 60)
    
    try:
        with open('server/services/email_service.py', 'r') as f:
            content = f.read()
        
        # Check if INSERT includes attachments column
        if 'attachments' not in content:
            print("❌ 'attachments' not found in email_service.py")
            return False
        
        # Check if INSERT statement includes attachments
        if 'INSERT INTO email_messages' in content and 'attachments' in content:
            # Find the INSERT statement
            insert_start = content.find('INSERT INTO email_messages')
            insert_section = content[insert_start:insert_start + 2000]
            
            if 'attachments' in insert_section:
                print("✅ INSERT statement includes 'attachments' column")
            else:
                print("❌ INSERT statement does NOT include 'attachments' column")
                return False
        
        # Check if attachment_ids parameter is used
        if 'attachment_ids' in content:
            print("✅ email_service.py handles attachment_ids parameter")
        else:
            print("⚠️  attachment_ids not explicitly handled")
        
        # Check if JSON encoding is used
        if 'json.dumps(attachment_ids)' in content or 'json.dumps(attachments)' in content:
            print("✅ Attachments are JSON-encoded before saving")
        else:
            print("⚠️  JSON encoding for attachments not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_frontend_attachment_picker():
    """Test that frontend has AttachmentPicker integrated"""
    print("\n" + "=" * 60)
    print("TEST: Frontend AttachmentPicker Integration")
    print("=" * 60)
    
    try:
        with open('client/src/pages/emails/EmailsPage.tsx', 'r') as f:
            content = f.read()
        
        # Check imports
        if 'AttachmentPicker' not in content:
            print("❌ AttachmentPicker not imported")
            return False
        
        print("✅ AttachmentPicker is imported")
        
        # Check if attachmentIds state exists
        if 'attachmentIds' in content:
            print("✅ attachmentIds state variable exists")
        else:
            print("❌ attachmentIds state not found")
            return False
        
        # Check if attachment_ids is sent to backend
        if 'attachment_ids' in content and 'attachmentIds' in content:
            print("✅ attachment_ids sent to backend")
        else:
            print("⚠️  attachment_ids sending to backend not found")
        
        # Check if AttachmentPicker component is rendered
        if '<AttachmentPicker' in content:
            print("✅ AttachmentPicker component is rendered")
        else:
            print("❌ AttachmentPicker component not rendered")
            return False
        
        # Check if selected attachments are displayed
        if 'קבצים מצורפים' in content or 'attachmentIds.length' in content:
            print("✅ Selected attachments are displayed to user")
        else:
            print("⚠️  Attachment display not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_r2_provider_config():
    """Test that R2 provider has correct configuration"""
    print("\n" + "=" * 60)
    print("TEST: R2 Provider Configuration")
    print("=" * 60)
    
    try:
        with open('server/services/storage/r2_provider.py', 'r') as f:
            content = f.read()
        
        checks = [
            ("region_name='auto'", "Region set to 'auto' (required for R2)"),
            ("signature_version='s3v4'", "Signature version set to 's3v4'"),
            ("addressing_style': 'path'", "Path-style addressing enabled"),
            ("retries", "Retry configuration present"),
            ("ContentType", "ContentType parameter in put_object")
        ]
        
        all_passed = True
        for check, description in checks:
            if check in content:
                print(f"✅ {description}")
            else:
                print(f"❌ {description} - NOT FOUND")
                all_passed = False
        
        # Check for logging
        if 'logger.info' in content and 'bucket=' in content:
            print("✅ Diagnostic logging present")
        else:
            print("⚠️  Diagnostic logging could be improved")
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_agent_warmup_schema():
    """Test that agent warmup schema issues are fixed"""
    print("\n" + "=" * 60)
    print("TEST: Agent Warmup Schema Fixes")
    print("=" * 60)
    
    try:
        # Check tools_crm_context.py for LeadData model
        with open('server/agent_tools/tools_crm_context.py', 'r') as f:
            content = f.read()
        
        if 'class LeadData(BaseModel):' in content:
            print("✅ LeadData Pydantic model defined (fixes dict schema issue)")
        else:
            print("❌ LeadData model not found")
            return False
        
        if 'lead: Optional[LeadData]' in content:
            print("✅ GetLeadContextOutput uses LeadData instead of dict")
        else:
            print("⚠️  GetLeadContextOutput might still use dict")
        
        # Check lazy_services.py for DISABLE_AGENT_WARMUP
        with open('server/services/lazy_services.py', 'r') as f:
            content = f.read()
        
        if 'DISABLE_AGENT_WARMUP' in content:
            print("✅ DISABLE_AGENT_WARMUP environment variable supported")
        else:
            print("❌ DISABLE_AGENT_WARMUP not implemented")
            return False
        
        if 'disable_agent_warmup' in content and 'if disable_agent_warmup:' in content:
            print("✅ Agent warmup can be skipped when env var is set")
        else:
            print("⚠️  Conditional warmup skip logic not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def main():
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "EMAIL ATTACHMENTS + R2 FIX VERIFICATION" + " " * 8 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    tests = [
        ("Migration 79 - Attachments Column", test_migration_79),
        ("Email Service - Attachments Support", test_email_service_attachments),
        ("Frontend - AttachmentPicker Integration", test_frontend_attachment_picker),
        ("R2 Provider - Configuration", test_r2_provider_config),
        ("Agent Warmup - Schema Fixes", test_agent_warmup_schema),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nNext steps:")
        print("1. Set environment variables for R2 (see .env.r2.example)")
        print("2. Run: python -m server.db_migrate (to apply Migration 79)")
        print("3. Optional: Set DISABLE_AGENT_WARMUP=1 if schema errors occur")
        print("4. Test file upload and email with attachments")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("Review the output above to fix issues")
        return 1


if __name__ == '__main__':
    sys.exit(main())
