#!/usr/bin/env python3
"""
Manual test to demonstrate Google Sheets webhook integration fix

This script simulates what happens when a webhook receives a Google Sheets payload.
Run this to verify the extraction logic works correctly with numeric phone values.

Usage:
    python3 tests/demo_webhook_fix.py
"""

def extract_lead_fields(payload):
    """
    Extract lead fields from webhook payload with support for flat and nested structures.
    This is the updated version with Google Sheets fixes.
    """
    if not isinstance(payload, dict):
        return {}
    
    result = {}
    
    # Build a unified flat view
    flat_payload = {}
    
    # Add all direct (non-dict) values
    for key, value in payload.items():
        if not isinstance(value, dict):
            flat_payload[key.lower()] = value
    
    # Check for nested "contact" object
    if 'contact' in payload and isinstance(payload['contact'], dict):
        contact_data = payload['contact']
        for key, value in contact_data.items():
            field_key = key.lower()
            if field_key not in flat_payload and not isinstance(value, dict):
                flat_payload[field_key] = value
    
    # Flatten other nested dicts with prefix
    for key, value in payload.items():
        if isinstance(value, dict) and key.lower() != 'contact':
            for nested_key, nested_value in value.items():
                prefixed_key = f"{key}_{nested_key}".lower()
                if prefixed_key not in flat_payload and not isinstance(nested_value, dict):
                    flat_payload[prefixed_key] = nested_value
    
    # Extract name
    name_fields = ['name', 'full_name', 'fullname', 'customer_name', 'contact_name']
    for field in name_fields:
        if field in flat_payload and flat_payload[field]:
            result['name'] = str(flat_payload[field]).strip()
            break
    
    # Try first_name + last_name
    if 'name' not in result:
        first_name = flat_payload.get('first_name') or flat_payload.get('firstname')
        last_name = flat_payload.get('last_name') or flat_payload.get('lastname')
        
        if first_name and last_name:
            result['name'] = f"{first_name} {last_name}".strip()
        elif first_name:
            result['name'] = str(first_name).strip()
        elif last_name:
            result['name'] = str(last_name).strip()
    
    # Extract phone with NEW aliases (whatsapp, phoneNumber)
    phone_fields = ['phone', 'phone_number', 'mobile', 'tel', 'whatsapp', 'phoneNumber', 'telephone', 'phonenumber', 'cell', 'cellphone']
    for field in phone_fields:
        if field in flat_payload and flat_payload[field]:
            phone_value = str(flat_payload[field]).strip()
            if phone_value:
                result['phone'] = phone_value
                break
    
    # Extract email
    email_fields = ['email', 'email_address', 'emailaddress', 'mail']
    for field in email_fields:
        if field in flat_payload and flat_payload[field]:
            email_value = str(flat_payload[field]).strip().lower()
            if email_value:
                result['email'] = email_value
                break
    
    # Extract source with NEW alias (utm_source)
    source_fields = ['source', 'utm_source', 'lead_source', 'origin']
    for field in source_fields:
        if field in flat_payload and flat_payload[field]:
            result['source'] = str(flat_payload[field]).strip()
            break
    
    return result


def demo_extraction(title, payload):
    """Demo extraction with a payload"""
    print(f"\n{'='*80}")
    print(f"🧪 {title}")
    print(f"{'='*80}")
    print(f"\n📥 Input Payload:")
    for key, value in payload.items():
        print(f"   {key}: {value!r} (type: {type(value).__name__})")
    
    # Extract fields
    fields = extract_lead_fields(payload)
    
    print(f"\n📤 Extracted Fields:")
    for key, value in fields.items():
        print(f"   {key}: {value!r}")
    
    # Extract phone digits
    import re
    phone_raw = fields.get('phone')
    phone_digits = None
    if phone_raw:
        phone_digits = re.sub(r'\D', '', str(phone_raw))
        print(f"\n📞 Phone Processing:")
        print(f"   phone_raw: {phone_raw!r}")
        print(f"   phone_digits: {phone_digits!r}")
    
    # Check validation
    email = fields.get('email')
    print(f"\n✅ Validation:")
    has_contact = bool(phone_digits or email)
    print(f"   Has phone_digits or email: {has_contact}")
    
    if has_contact:
        print(f"   ✅ Would CREATE lead successfully")
    else:
        print(f"   ❌ Would REJECT - missing contact identifier")
    
    return fields


if __name__ == "__main__":
    print("="*80)
    print("🎯 GOOGLE SHEETS WEBHOOK FIX - DEMONSTRATION")
    print("="*80)
    print("\nThis demonstrates the fix for webhook lead extraction with Google Sheets")
    print("payloads where phone numbers arrive as numeric types (int) instead of strings.")
    
    # Test 1: Original problem - Google Sheets numeric phone
    demo_extraction(
        "Test 1: Google Sheets Payload (ORIGINAL PROBLEM)",
        {
            "name": "צוריאל ארביב",
            "email": "tzurielarviv@gmail.com",
            "phone": 549750505,  # ⚠️ NUMERIC - this was failing before
            "source": "google_sheet"
        }
    )
    
    # Test 2: WhatsApp field alias
    demo_extraction(
        "Test 2: WhatsApp Field Alias (NEW)",
        {
            "name": "John Doe",
            "whatsapp": "+972501234567",  # 🆕 NEW alias support
            "email": "john@example.com"
        }
    )
    
    # Test 3: phoneNumber camelCase
    demo_extraction(
        "Test 3: phoneNumber CamelCase (NEW)",
        {
            "name": "Jane Smith",
            "phoneNumber": "0541234567",  # 🆕 NEW camelCase support
            "email": "jane@example.com"
        }
    )
    
    # Test 4: utm_source alias
    demo_extraction(
        "Test 4: utm_source Alias (NEW)",
        {
            "name": "Marketing Lead",
            "phone": "0521234567",
            "utm_source": "facebook_ads"  # 🆕 NEW source alias
        }
    )
    
    # Test 5: Phone without leading zero (Google Sheets issue)
    demo_extraction(
        "Test 5: Phone Without Leading Zero",
        {
            "name": "Israeli Lead",
            "phone": 549750505,  # Missing leading 0 (0549750505)
            "email": "lead@example.com"
        }
    )
    
    print("\n" + "="*80)
    print("✅ ALL DEMONSTRATIONS COMPLETED")
    print("="*80)
    print("\n📝 Summary of Fixes:")
    print("   1. ✅ Numeric phone values (int/float) converted to string")
    print("   2. ✅ New phone aliases: whatsapp, phoneNumber (camelCase)")
    print("   3. ✅ New source aliases: utm_source")
    print("   4. ✅ phone_digits extraction using regex")
    print("   5. ✅ Validation on phone_digits OR email (not blocking)")
    print("   6. ✅ Enhanced logging with phone_raw, phone_digits, phone_e164")
    print()
