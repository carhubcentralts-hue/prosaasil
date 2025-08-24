#!/usr/bin/env python3
"""
Deployment Validation Script for AgentLocator 71
Validates that deployed code is actually running latest version
"""
import os
import sys
import json
import requests
import time
from datetime import datetime

def validate_deployment(base_url):
    """Run complete deployment validation"""
    
    print(f"🔍 **AgentLocator 71 - Deployment Validation**")
    print(f"Target: {base_url}")
    print(f"Time: {datetime.now().isoformat()}")
    print("-" * 60)
    
    results = {}
    
    # 1. Version Check
    print("1️⃣ **Version Check:**")
    try:
        resp = requests.get(f"{base_url}/version", timeout=10)
        if resp.status_code == 200:
            version_data = resp.json()
            print(f"   ✅ commit: {version_data.get('commit', 'N/A')}")
            print(f"   ✅ build_time: {version_data.get('build_time', 'N/A')}")
            print(f"   ✅ deploy_id: {version_data.get('deploy_id', 'N/A')}")
            print(f"   ✅ timestamp: {version_data.get('ts', 'N/A')}")
            results['version'] = 'PASS'
        else:
            print(f"   ❌ /version returned {resp.status_code}")
            results['version'] = 'FAIL'
    except Exception as e:
        print(f"   ❌ Version check failed: {e}")
        results['version'] = 'FAIL'
    
    # 2. TwiML Cache Headers
    print("\n2️⃣ **TwiML Cache Headers:**")
    try:
        resp = requests.post(f"{base_url}/webhook/incoming_call", 
                           data={"CallSid": "VALIDATION_TEST"}, 
                           timeout=10)
        cache_control = resp.headers.get('Cache-Control', '')
        if 'no-store' in cache_control and 'no-cache' in cache_control:
            print(f"   ✅ Cache-Control: {cache_control}")
            results['cache_headers'] = 'PASS'
        else:
            print(f"   ❌ Missing cache busting: {cache_control}")
            results['cache_headers'] = 'FAIL'
    except Exception as e:
        print(f"   ❌ TwiML cache test failed: {e}")
        results['cache_headers'] = 'FAIL'
    
    # 3. Static MP3 Files
    print("\n3️⃣ **Static MP3 Files:**")
    mp3_files = [
        "/static/tts/greeting_he.mp3",
        "/static/tts/fallback_he.mp3"
    ]
    
    for mp3_path in mp3_files:
        try:
            resp = requests.head(f"{base_url}{mp3_path}", timeout=10)
            if resp.status_code == 200:
                size = resp.headers.get('Content-Length', 'Unknown')
                print(f"   ✅ {mp3_path}: {resp.status_code} ({size} bytes)")
            else:
                print(f"   ❌ {mp3_path}: {resp.status_code}")
                results['static_files'] = 'FAIL'
        except Exception as e:
            print(f"   ❌ {mp3_path}: {e}")
            results['static_files'] = 'FAIL'
    
    if 'static_files' not in results:
        results['static_files'] = 'PASS'
    
    # 4. Health Endpoints
    print("\n4️⃣ **Health Endpoints:**")
    health_endpoints = ["/healthz", "/readyz"]
    
    for endpoint in health_endpoints:
        try:
            resp = requests.get(f"{base_url}{endpoint}", timeout=10)
            if resp.status_code == 200:
                print(f"   ✅ {endpoint}: {resp.status_code}")
            else:
                print(f"   ❌ {endpoint}: {resp.status_code}")
                results['health'] = 'FAIL'
        except Exception as e:
            print(f"   ❌ {endpoint}: {e}")
            results['health'] = 'FAIL'
    
    if 'health' not in results:
        results['health'] = 'PASS'
    
    # 5. TwiML Structure
    print("\n5️⃣ **TwiML Structure:**")
    try:
        resp = requests.post(f"{base_url}/webhook/incoming_call", 
                           data={"CallSid": "STRUCTURE_TEST"}, 
                           timeout=10)
        twiml_content = resp.text
        
        checks = [
            ("<Connect>", "Connect element"),
            ("<Stream", "Stream element"),
            ("statusCallback", "Status callback"),
            ("ws/twilio-media", "WebSocket URL")
        ]
        
        structure_ok = True
        for check, desc in checks:
            if check in twiml_content:
                print(f"   ✅ {desc}: Found")
            else:
                print(f"   ❌ {desc}: Missing")
                structure_ok = False
        
        results['twiml_structure'] = 'PASS' if structure_ok else 'FAIL'
        
    except Exception as e:
        print(f"   ❌ TwiML structure test failed: {e}")
        results['twiml_structure'] = 'FAIL'
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 **VALIDATION SUMMARY:**")
    
    all_passed = True
    for test, result in results.items():
        status = "✅ PASS" if result == 'PASS' else "❌ FAIL"
        print(f"   {test.replace('_', ' ').title()}: {status}")
        if result == 'FAIL':
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("🎉 **DEPLOYMENT SUCCESSFUL - All validations passed!**")
        return True
    else:
        print("🚨 **DEPLOYMENT ISSUES - Some validations failed!**")
        return False

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "https://ai-crmd.replit.app"
    success = validate_deployment(base_url)
    sys.exit(0 if success else 1)