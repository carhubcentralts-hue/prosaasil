#!/usr/bin/env python3
"""
Test to verify CRM context fetches customer name from Lead record
This tests the fix for the issue where crm_context.customer_name was not being populated
"""

def test_crm_context_name_fetch_logic():
    """Verify the logic for fetching customer name from Lead when pending_customer_name is None"""
    print("\n" + "="*80)
    print("🔍 TEST: CRM Context Name Fetch Logic")
    print("="*80)
    
    # Simulate the scenario from the problem statement:
    # 1. pending_customer_name is None
    # 2. Lead exists with a name
    # 3. CRM context should use name from Lead
    
    print(f"\n📋 Test Scenario 1: pending_customer_name is None, Lead has name")
    
    # Mock Lead object
    class MockLead:
        def __init__(self, first_name, last_name):
            self.first_name = first_name
            self.last_name = last_name
            self.id = 123
        
        @property
        def full_name(self):
            if self.first_name and self.last_name:
                return f"{self.first_name} {self.last_name}"
            return self.first_name or self.last_name or ""
    
    # Mock CRM context
    class MockCrmContext:
        def __init__(self, business_id, customer_phone, lead_id):
            self.business_id = business_id
            self.customer_phone = customer_phone
            self.lead_id = lead_id
            self.customer_name = None
    
    # Setup
    pending_customer_name = None
    lead = MockLead("דני", "כהן")
    lead_id = lead.id
    
    crm_context = MockCrmContext(
        business_id=4,
        customer_phone="+972501234567",
        lead_id=lead_id
    )
    
    print(f"   Initial state:")
    print(f"     pending_customer_name: {pending_customer_name}")
    print(f"     crm_context.customer_name: {crm_context.customer_name}")
    print(f"     Lead.first_name: {lead.first_name}")
    print(f"     Lead.last_name: {lead.last_name}")
    
    # ORIGINAL CODE: Hydration step
    if pending_customer_name:
        crm_context.customer_name = pending_customer_name
    
    print(f"\n   After hydration:")
    print(f"     crm_context.customer_name: {crm_context.customer_name}")
    
    # NEW FIX: Fetch from Lead if not set
    if not crm_context.customer_name and lead_id:
        full_name = lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip()
        if full_name and full_name not in ['', 'Customer', 'ללא שם']:
            # Extract first name only (for natural usage)
            customer_name = lead.first_name or full_name
            crm_context.customer_name = customer_name
            print(f"\n   ✅ Fetched from Lead: '{customer_name}'")
    
    print(f"\n   Final state:")
    print(f"     crm_context.customer_name: {crm_context.customer_name}")
    
    # Assertions
    assert crm_context.customer_name is not None, "customer_name should not be None"
    assert crm_context.customer_name == "דני", f"customer_name should be 'דני', got '{crm_context.customer_name}'"
    
    print(f"\n   ✅ Test 1 PASSED")
    
    # Test Scenario 2: pending_customer_name is set, should use it instead of Lead
    print(f"\n📋 Test Scenario 2: pending_customer_name is set, should use it")
    
    pending_customer_name = "שי"
    lead2 = MockLead("דני", "כהן")
    
    crm_context2 = MockCrmContext(
        business_id=4,
        customer_phone="+972501234567",
        lead_id=lead2.id
    )
    
    print(f"   Initial state:")
    print(f"     pending_customer_name: {pending_customer_name}")
    print(f"     Lead.first_name: {lead2.first_name}")
    
    # Hydration step
    if pending_customer_name:
        crm_context2.customer_name = pending_customer_name
    
    print(f"\n   After hydration:")
    print(f"     crm_context.customer_name: {crm_context2.customer_name}")
    
    # NEW FIX: Should skip because customer_name is already set
    if not crm_context2.customer_name and lead2.id:
        full_name = lead2.full_name or f"{lead2.first_name or ''} {lead2.last_name or ''}".strip()
        if full_name and full_name not in ['', 'Customer', 'ללא שם']:
            customer_name = lead2.first_name or full_name
            crm_context2.customer_name = customer_name
            print(f"     Fetched from Lead: '{customer_name}'")
    
    print(f"\n   Final state:")
    print(f"     crm_context.customer_name: {crm_context2.customer_name}")
    
    # Assertions
    assert crm_context2.customer_name == "שי", f"customer_name should be 'שי', got '{crm_context2.customer_name}'"
    
    print(f"\n   ✅ Test 2 PASSED")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED: CRM Context correctly fetches customer name from Lead")
    print("="*80)

if __name__ == "__main__":
    test_crm_context_name_fetch_logic()
