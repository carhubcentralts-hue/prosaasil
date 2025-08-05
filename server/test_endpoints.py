"""
Quick test for AgentLocator API endpoints
טסט מהיר לבדיקת endpoints של AgentLocator
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_endpoint(url, method="GET", data=None):
    """Test a single endpoint"""
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{url}")
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{url}", json=data)
        
        print(f"🔍 {method} {url}")
        print(f"   Status: {response.status_code}")
        
        if response.headers.get('content-type', '').startswith('application/json'):
            try:
                data = response.json()
                print(f"   Response: {json.dumps(data, indent=2, ensure_ascii=False)[:200]}...")
            except:
                print(f"   Response: {response.text[:200]}...")
        else:
            print(f"   Response: {response.text[:200]}...")
        print()
        
    except Exception as e:
        print(f"❌ Error testing {url}: {e}")
        print()

def main():
    """Test all AgentLocator endpoints"""
    print("🧪 Testing AgentLocator API Endpoints")
    print("=" * 50)
    
    endpoints = [
        "/api/crm/customers",
        "/api/crm/tasks",
        "/api/whatsapp/conversations", 
        "/api/signature/signatures",
        "/api/proposal/proposals",
        "/api/invoice/invoices",
        "/api/stats/overview"
    ]
    
    for endpoint in endpoints:
        test_endpoint(endpoint)
    
    print("🎯 Test completed!")

if __name__ == "__main__":
    main()