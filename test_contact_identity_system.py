"""
🎯 BUILD 200: Tests for Unified Contact Identity System

Tests verify that the contact identity system correctly:
1. Creates leads for WhatsApp messages
2. Prevents duplicate leads when same person messages again
3. Creates leads for phone calls
4. Links leads across channels when same phone number is detected
5. Respects name_source priority (user_provided > call/whatsapp)

## Running Tests

These tests require the full Python environment with Flask and database access.

### Local Development:
```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests
python test_contact_identity_system.py
```

### Production Environment:
```bash
# Run via Docker with database access
docker-compose exec prosaas-api python test_contact_identity_system.py
```

## Manual Testing

If automated tests cannot run, verify manually:

1. **WhatsApp Message** → Check Lead created with correct phone/JID
2. **Second WhatsApp** → Verify same lead_id returned (no duplicate)
3. **Phone Call** → Check Lead created with normalized phone
4. **Cross-Channel** → WhatsApp then Call → Same lead_id
5. **Name Priority** → Manual name not overwritten by push_name/caller_name
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_whatsapp_lead_creation():
    """
    Test 1: WhatsApp message from new contact creates lead correctly
    """
    print("\n" + "="*80)
    print("TEST 1: WhatsApp message creates lead correctly")
    print("="*80)
    
    from server.app_factory import create_minimal_app
    from server.services.contact_identity_service import ContactIdentityService
    from server.models_sql import Lead, ContactIdentity, Business
    from server.db import db
    
    app = create_minimal_app()
    
    with app.app_context():
        # Setup: Ensure we have a test business
        business = Business.query.first()
        if not business:
            print("❌ No business found - create one first")
            return False
        
        business_id = business.id
        test_jid = "972525951893@s.whatsapp.net"
        test_push_name = "Test User"
        
        print(f"📝 Creating lead for: biz={business_id}, jid={test_jid}, push_name={test_push_name}")
        
        # Clean up any existing test data
        ContactIdentity.query.filter_by(
            business_id=business_id,
            external_id=test_jid
        ).delete()
        
        existing_lead = Lead.query.filter_by(
            tenant_id=business_id,
            phone_e164="+972525951893"
        ).first()
        if existing_lead:
            ContactIdentity.query.filter_by(lead_id=existing_lead.id).delete()
            db.session.delete(existing_lead)
        
        db.session.commit()
        
        # Test: Create lead for WhatsApp message
        lead = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business_id,
            remote_jid=test_jid,
            push_name=test_push_name,
            message_text="היי, אני מעוניין במידע",
            wa_message_id="test_msg_001"
        )
        
        # Verify lead was created
        assert lead is not None, "Lead should be created"
        assert lead.tenant_id == business_id, "Lead should belong to correct business"
        assert lead.phone_e164 == "+972525951893", "Phone should be normalized to E.164"
        assert lead.source == "whatsapp", "Source should be whatsapp"
        assert lead.whatsapp_jid == test_jid, "WhatsApp JID should be saved"
        assert lead.name == test_push_name, "Name should be set from push_name"
        assert lead.name_source == "whatsapp", "Name source should be whatsapp"
        
        # Verify contact identity mapping was created
        identity = ContactIdentity.query.filter_by(
            business_id=business_id,
            channel='whatsapp',
            external_id=test_jid
        ).first()
        
        assert identity is not None, "Contact identity mapping should be created"
        assert identity.lead_id == lead.id, "Identity should map to correct lead"
        
        print(f"✅ Lead created successfully: lead_id={lead.id}, phone={lead.phone_e164}")
        print(f"✅ Contact identity mapping created: identity_id={identity.id}")
        
        return True


def test_whatsapp_no_duplicate():
    """
    Test 2: Second WhatsApp message from same JID doesn't create duplicate lead
    """
    print("\n" + "="*80)
    print("TEST 2: Second WhatsApp message doesn't create duplicate")
    print("="*80)
    
    from server.app_factory import create_minimal_app
    from server.services.contact_identity_service import ContactIdentityService
    from server.models_sql import Lead, ContactIdentity, Business
    from server.db import db
    
    app = create_minimal_app()
    
    with app.app_context():
        business = Business.query.first()
        business_id = business.id
        test_jid = "972525951894@s.whatsapp.net"
        
        # Clean up
        ContactIdentity.query.filter_by(
            business_id=business_id,
            external_id=test_jid
        ).delete()
        existing_lead = Lead.query.filter_by(
            tenant_id=business_id,
            phone_e164="+972525951894"
        ).first()
        if existing_lead:
            ContactIdentity.query.filter_by(lead_id=existing_lead.id).delete()
            db.session.delete(existing_lead)
        db.session.commit()
        
        # Create first message - should create lead
        lead1 = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business_id,
            remote_jid=test_jid,
            push_name="User A",
            message_text="הודעה ראשונה",
            wa_message_id="msg_001"
        )
        
        lead1_id = lead1.id
        print(f"📝 First message created: lead_id={lead1_id}")
        
        # Create second message - should return same lead
        lead2 = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business_id,
            remote_jid=test_jid,
            push_name="User A",
            message_text="הודעה שנייה",
            wa_message_id="msg_002"
        )
        
        lead2_id = lead2.id
        print(f"📝 Second message returned: lead_id={lead2_id}")
        
        # Verify same lead was returned
        assert lead2_id == lead1_id, f"Should return same lead: {lead1_id} vs {lead2_id}"
        
        # Verify no duplicate contact identities
        identity_count = ContactIdentity.query.filter_by(
            business_id=business_id,
            channel='whatsapp',
            external_id=test_jid
        ).count()
        
        assert identity_count == 1, f"Should have exactly 1 identity mapping, found {identity_count}"
        
        print(f"✅ No duplicate created - same lead returned: lead_id={lead2_id}")
        
        return True


def test_phone_call_lead_creation():
    """
    Test 3: Phone call creates lead correctly
    """
    print("\n" + "="*80)
    print("TEST 3: Phone call creates lead correctly")
    print("="*80)
    
    from server.app_factory import create_minimal_app
    from server.services.contact_identity_service import ContactIdentityService
    from server.models_sql import Lead, ContactIdentity, Business
    from server.db import db
    
    app = create_minimal_app()
    
    with app.app_context():
        business = Business.query.first()
        business_id = business.id
        test_phone = "+972525951895"
        test_caller_name = "דוד כהן"
        
        # Clean up
        ContactIdentity.query.filter_by(
            business_id=business_id,
            external_id=test_phone
        ).delete()
        existing_lead = Lead.query.filter_by(
            tenant_id=business_id,
            phone_e164=test_phone
        ).first()
        if existing_lead:
            ContactIdentity.query.filter_by(lead_id=existing_lead.id).delete()
            db.session.delete(existing_lead)
        db.session.commit()
        
        print(f"📝 Creating lead for: biz={business_id}, phone={test_phone}, caller={test_caller_name}")
        
        # Test: Create lead for phone call
        lead = ContactIdentityService.get_or_create_lead_for_call(
            business_id=business_id,
            from_e164=test_phone,
            caller_name=test_caller_name,
            call_sid="CA_test_001"
        )
        
        # Verify lead was created
        assert lead is not None, "Lead should be created"
        assert lead.tenant_id == business_id, "Lead should belong to correct business"
        assert lead.phone_e164 == test_phone, "Phone should match"
        assert lead.source == "call", "Source should be call"
        assert lead.name == test_caller_name, "Name should be set from caller_name"
        assert lead.name_source == "call", "Name source should be call"
        
        # Verify contact identity mapping was created
        identity = ContactIdentity.query.filter_by(
            business_id=business_id,
            channel='phone',
            external_id=test_phone
        ).first()
        
        assert identity is not None, "Contact identity mapping should be created"
        assert identity.lead_id == lead.id, "Identity should map to correct lead"
        
        print(f"✅ Lead created successfully: lead_id={lead.id}, phone={lead.phone_e164}")
        print(f"✅ Contact identity mapping created: identity_id={identity.id}")
        
        return True


def test_cross_channel_linking():
    """
    Test 4: Same person via WhatsApp + Phone links to one lead
    """
    print("\n" + "="*80)
    print("TEST 4: Cross-channel linking (WhatsApp + Phone → same lead)")
    print("="*80)
    
    from server.app_factory import create_minimal_app
    from server.services.contact_identity_service import ContactIdentityService
    from server.models_sql import Lead, ContactIdentity, Business
    from server.db import db
    
    app = create_minimal_app()
    
    with app.app_context():
        business = Business.query.first()
        business_id = business.id
        test_phone = "+972525951896"
        test_jid = "972525951896@s.whatsapp.net"
        
        # Clean up
        for channel in ['whatsapp', 'phone']:
            external_id = test_jid if channel == 'whatsapp' else test_phone
            ContactIdentity.query.filter_by(
                business_id=business_id,
                channel=channel,
                external_id=external_id
            ).delete()
        
        existing_lead = Lead.query.filter_by(
            tenant_id=business_id,
            phone_e164=test_phone
        ).first()
        if existing_lead:
            ContactIdentity.query.filter_by(lead_id=existing_lead.id).delete()
            db.session.delete(existing_lead)
        db.session.commit()
        
        # Step 1: WhatsApp message creates lead
        print(f"📝 Step 1: WhatsApp message from {test_jid}")
        lead_wa = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business_id,
            remote_jid=test_jid,
            push_name="משתמש מבחן",
            message_text="היי",
            wa_message_id="msg_wa_001"
        )
        
        lead_wa_id = lead_wa.id
        print(f"   → Created lead_id={lead_wa_id}")
        
        # Step 2: Phone call should link to same lead
        print(f"📝 Step 2: Phone call from {test_phone} (same number)")
        lead_call = ContactIdentityService.get_or_create_lead_for_call(
            business_id=business_id,
            from_e164=test_phone,
            caller_name="משתמש מבחן",
            call_sid="CA_test_002"
        )
        
        lead_call_id = lead_call.id
        print(f"   → Returned lead_id={lead_call_id}")
        
        # Verify same lead was used
        assert lead_call_id == lead_wa_id, f"Should link to same lead: {lead_wa_id} vs {lead_call_id}"
        
        # Verify TWO contact identities exist (one per channel)
        identities = ContactIdentity.query.filter_by(
            business_id=business_id,
            lead_id=lead_wa_id
        ).all()
        
        assert len(identities) == 2, f"Should have 2 identities (whatsapp + phone), found {len(identities)}"
        
        channels = {i.channel for i in identities}
        assert 'whatsapp' in channels, "Should have whatsapp identity"
        assert 'phone' in channels, "Should have phone identity"
        
        print(f"✅ Cross-channel linking successful!")
        print(f"   → Single lead: lead_id={lead_wa_id}")
        print(f"   → Two identity mappings: whatsapp + phone")
        
        return True


def test_name_source_priority():
    """
    Test 5: name_source='user_provided' is not overwritten by whatsapp/call
    """
    print("\n" + "="*80)
    print("TEST 5: name_source='user_provided' not overwritten")
    print("="*80)
    
    from server.app_factory import create_minimal_app
    from server.services.contact_identity_service import ContactIdentityService
    from server.models_sql import Lead, ContactIdentity, Business
    from server.db import db
    from datetime import datetime
    
    app = create_minimal_app()
    
    with app.app_context():
        business = Business.query.first()
        business_id = business.id
        test_jid = "972525951897@s.whatsapp.net"
        test_phone = "+972525951897"
        
        # Clean up
        ContactIdentity.query.filter_by(
            business_id=business_id,
            external_id=test_jid
        ).delete()
        existing_lead = Lead.query.filter_by(
            tenant_id=business_id,
            phone_e164=test_phone
        ).first()
        if existing_lead:
            ContactIdentity.query.filter_by(lead_id=existing_lead.id).delete()
            db.session.delete(existing_lead)
        db.session.commit()
        
        # Step 1: Create lead via WhatsApp
        print(f"📝 Step 1: Create lead via WhatsApp with push_name='אוטומטי'")
        lead = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business_id,
            remote_jid=test_jid,
            push_name="אוטומטי",
            message_text="היי",
            wa_message_id="msg_001"
        )
        
        print(f"   → Lead created: name='{lead.name}', name_source='{lead.name_source}'")
        assert lead.name == "אוטומטי", "Name should be set from push_name"
        assert lead.name_source == "whatsapp", "Name source should be whatsapp"
        
        # Step 2: Manually update name to user_provided
        print(f"📝 Step 2: Manually update name to 'יוסי לוי' (name_source=user_provided)")
        lead.name = "יוסי לוי"
        lead.name_source = "user_provided"
        lead.name_updated_at = datetime.utcnow()
        db.session.commit()
        
        # Step 3: New WhatsApp message with different push_name
        print(f"📝 Step 3: New WhatsApp message with push_name='אוטומטי חדש'")
        lead_updated = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business_id,
            remote_jid=test_jid,
            push_name="אוטומטי חדש",
            message_text="הודעה נוספת",
            wa_message_id="msg_002"
        )
        
        # Verify name was NOT overwritten
        assert lead_updated.id == lead.id, "Should return same lead"
        assert lead_updated.name == "יוסי לוי", f"Name should NOT change, got '{lead_updated.name}'"
        assert lead_updated.name_source == "user_provided", "Name source should remain user_provided"
        
        print(f"✅ user_provided name protected!")
        print(f"   → Name remained: '{lead_updated.name}' (not overwritten by '{' אוטומטי חדש'}')")
        
        return True


if __name__ == '__main__':
    print("\n" + "="*80)
    print("🎯 BUILD 200: Contact Identity System Tests")
    print("="*80)
    
    tests = [
        ("WhatsApp lead creation", test_whatsapp_lead_creation),
        ("No duplicate WhatsApp leads", test_whatsapp_no_duplicate),
        ("Phone call lead creation", test_phone_call_lead_creation),
        ("Cross-channel linking", test_cross_channel_linking),
        ("Name source priority", test_name_source_priority),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} tests failed")
        sys.exit(1)
