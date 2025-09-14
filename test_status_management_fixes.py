#!/usr/bin/env python3
"""
Test script to verify status management data integrity fixes
"""
import requests
import json
import sys

BASE_URL = "http://localhost:5000"
session = requests.Session()

def get_csrf_token():
    """Get CSRF token for authenticated requests"""
    response = session.get(f"{BASE_URL}/api/auth/csrf")
    if response.status_code == 200:
        return response.json()["csrfToken"]
    return None

def login_as_admin():
    """Login as admin user (assuming default admin credentials)"""
    csrf_token = get_csrf_token()
    if not csrf_token:
        print("❌ Failed to get CSRF token")
        return False
    
    headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf_token
    }
    
    # Try with the correct admin credentials from server/auth_api.py
    login_data = {
        'email': 'admin@shai-realestate.co.il',
        'password': 'admin123'
    }
    
    response = session.post(f"{BASE_URL}/api/auth/login", 
                          json=login_data, 
                          headers=headers)
    
    print(f"Login attempt: {response.status_code}")
    if response.status_code == 200:
        print("✅ Logged in successfully")
        return True
    else:
        print(f"❌ Login failed: {response.text}")
        return False

def test_auto_seeding():
    """Test that GET /api/statuses auto-seeds default statuses when empty"""
    print("\n🧪 Testing auto-seeding...")
    
    response = session.get(f"{BASE_URL}/api/statuses")
    print(f"GET /api/statuses status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        statuses = data.get('items', [])
        print(f"✅ Got {len(statuses)} statuses")
        
        # Check if we got the expected default statuses
        expected_statuses = ['new', 'attempting', 'contacted', 'qualified', 'won', 'lost', 'unqualified']
        actual_status_names = [s['name'] for s in statuses]
        
        for expected in expected_statuses:
            if expected in actual_status_names:
                print(f"✅ Found expected status: {expected}")
            else:
                print(f"❌ Missing expected status: {expected}")
        
        return statuses
    else:
        print(f"❌ Failed to get statuses: {response.text}")
        return []

def test_deletion_protection(statuses):
    """Test that DELETE returns 409 when status is in use"""
    print("\n🧪 Testing deletion protection...")
    
    if not statuses:
        print("❌ No statuses to test with")
        return
    
    # Get CSRF token for delete request
    csrf_token = get_csrf_token()
    headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf_token
    }
    
    # Try to delete the first status (assuming it might be in use)
    status_to_delete = statuses[0]
    print(f"Attempting to delete status: {status_to_delete['name']} (ID: {status_to_delete['id']})")
    
    response = session.delete(f"{BASE_URL}/api/statuses/{status_to_delete['id']}", 
                            headers=headers)
    
    print(f"DELETE status response: {response.status_code}")
    if response.status_code == 409:
        data = response.json()
        print(f"✅ Got expected 409 Conflict: {data.get('error', 'No error message')}")
        if 'lead_count' in data:
            print(f"✅ Lead count provided: {data['lead_count']}")
    elif response.status_code == 403:
        print(f"✅ Got 403 Forbidden (system status or default protection): {response.json().get('error')}")
    elif response.status_code == 200:
        print(f"⚠️  Got 200 OK - status was actually deleted: {response.json()}")
    else:
        print(f"❌ Unexpected response: {response.status_code} - {response.text}")

def test_default_status_protection(statuses):
    """Test that default status cannot be deleted without another default"""
    print("\n🧪 Testing default status protection...")
    
    # Find the default status
    default_status = None
    for status in statuses:
        if status.get('is_default'):
            default_status = status
            break
    
    if not default_status:
        print("❌ No default status found")
        return
    
    print(f"Found default status: {default_status['name']} (ID: {default_status['id']})")
    
    # Get CSRF token for delete request
    csrf_token = get_csrf_token()
    headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf_token
    }
    
    response = session.delete(f"{BASE_URL}/api/statuses/{default_status['id']}", 
                            headers=headers)
    
    print(f"DELETE default status response: {response.status_code}")
    if response.status_code == 409:
        data = response.json()
        error_msg = data.get('error', '')
        if 'default' in error_msg.lower():
            print(f"✅ Got expected default status protection: {error_msg}")
        else:
            print(f"⚠️  Got 409 but not for default reason: {error_msg}")
    else:
        print(f"❌ Expected 409 but got {response.status_code}: {response.text}")

def main():
    print("🧪 Testing Status Management Data Integrity Fixes")
    print("=" * 50)
    
    # Login is required for the API endpoints
    if not login_as_admin():
        print("❌ Cannot proceed without authentication")
        sys.exit(1)
    
    # Test auto-seeding
    statuses = test_auto_seeding()
    
    # Test deletion protection
    test_deletion_protection(statuses)
    
    # Test default status protection
    test_default_status_protection(statuses)
    
    print("\n✅ Testing completed!")

if __name__ == "__main__":
    main()