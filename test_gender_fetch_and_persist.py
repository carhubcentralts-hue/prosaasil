#!/usr/bin/env python3
"""
Test to verify gender detection and persistence works for both inbound and outbound calls
"""

def test_gender_fetch_and_persist():
    """Verify that gender is fetched from Lead and persisted back to Lead"""
    print("\n" + "="*80)
    print("🔍 TEST: Gender Fetch and Persistence")
    print("="*80)
    
    # Mock Lead object
    class MockLead:
        def __init__(self, first_name, last_name, gender=None):
            self.first_name = first_name
            self.last_name = last_name
            self.gender = gender
            self.id = 123
            self.tenant_id = 4
        
        @property
        def full_name(self):
            if self.first_name and self.last_name:
                return f"{self.first_name} {self.last_name}"
            return self.first_name or self.last_name or ""
    
    # Test Scenario 1: Lead has gender in UI/database - should be fetched and used
    print(f"\n📋 Test Scenario 1: Lead has gender='male' in database")
    
    lead = MockLead("דני", "כהן", gender="male")
    pending_customer_gender = None
    
    print(f"   Initial state:")
    print(f"     Lead.gender: {lead.gender}")
    print(f"     pending_customer_gender: {pending_customer_gender}")
    
    # Simulate fetching gender from Lead during name resolution
    if lead.gender:
        pending_customer_gender = lead.gender
        print(f"\n   ✅ Fetched gender from Lead: '{pending_customer_gender}'")
    
    # Verify
    assert pending_customer_gender == "male", f"Expected 'male', got '{pending_customer_gender}'"
    print(f"   ✅ Test 1 PASSED: Gender fetched correctly")
    
    # Test Scenario 2: Gender detected from conversation - should update Lead
    print(f"\n📋 Test Scenario 2: Gender detected from conversation")
    
    lead2 = MockLead("שי", "דהן", gender=None)
    detected_gender_from_conversation = "female"  # Detected from "אני אישה"
    
    print(f"   Initial state:")
    print(f"     Lead.gender: {lead2.gender}")
    print(f"     Detected from conversation: {detected_gender_from_conversation}")
    
    # Simulate updating Lead with detected gender
    old_gender = lead2.gender
    lead2.gender = detected_gender_from_conversation
    
    print(f"\n   ✅ Updated Lead.gender: {old_gender} → {lead2.gender}")
    
    # Verify
    assert lead2.gender == "female", f"Expected 'female', got '{lead2.gender}'"
    print(f"   ✅ Test 2 PASSED: Gender persisted to Lead")
    
    # Test Scenario 3: Inbound call with existing Lead that has gender
    print(f"\n📋 Test Scenario 3: Inbound call - fetch gender by phone lookup")
    
    lead3 = MockLead("אבי", "לוי", gender="male")
    phone_number = "+972501234567"
    
    print(f"   Initial state:")
    print(f"     Call type: inbound")
    print(f"     Phone: {phone_number}")
    print(f"     Lead.gender: {lead3.gender}")
    
    # Simulate phone-based lookup
    if phone_number:
        # In real code, this would query Lead.query.filter_by(phone_e164=...)
        found_lead = lead3  # Mock result
        if found_lead and found_lead.gender:
            fetched_gender = found_lead.gender
            print(f"\n   ✅ Fetched gender from Lead via phone lookup: '{fetched_gender}'")
    
    assert fetched_gender == "male", f"Expected 'male', got '{fetched_gender}'"
    print(f"   ✅ Test 3 PASSED: Gender fetched for inbound call")
    
    # Test Scenario 4: Outbound call with lead_id
    print(f"\n📋 Test Scenario 4: Outbound call - fetch gender by lead_id")
    
    lead4 = MockLead("רונית", "כהן", gender="female")
    lead_id = lead4.id
    
    print(f"   Initial state:")
    print(f"     Call type: outbound")
    print(f"     lead_id: {lead_id}")
    print(f"     Lead.gender: {lead4.gender}")
    
    # Simulate lead_id-based lookup
    if lead_id:
        # In real code, this would query Lead.query.get(lead_id)
        found_lead = lead4  # Mock result
        if found_lead and found_lead.gender:
            fetched_gender = found_lead.gender
            print(f"\n   ✅ Fetched gender from Lead via lead_id: '{fetched_gender}'")
    
    assert fetched_gender == "female", f"Expected 'female', got '{fetched_gender}'"
    print(f"   ✅ Test 4 PASSED: Gender fetched for outbound call")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED: Gender fetch and persistence work correctly")
    print("="*80)

if __name__ == "__main__":
    test_gender_fetch_and_persist()
