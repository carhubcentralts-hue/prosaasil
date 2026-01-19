#!/usr/bin/env python3
"""
Test WhatsApp Bot Context Retention Fix
"""

import sys
import os

def test_conversation_history_limit():
    print("\n" + "="*80)
    print("🔍 TEST 1: Conversation History Limit Increased to 12 Messages")
    print("="*80)
    
    with open('server/services/ai_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'prev_msgs[-12:]' in content:
        print("✅ PASS: History limit increased to 12 messages")
        return True
    else:
        print("❌ FAIL: Expected to find prev_msgs[-12:]")
        return False

def test_database_query_limit():
    print("\n" + "="*80)
    print("🔍 TEST 2: Database Query Limit Increased to 12 Messages")
    print("="*80)
    
    with open('server/routes_whatsapp.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if '.limit(12).all()' in content:
        print("✅ PASS: Database query limit increased to 12")
        return True
    else:
        print("❌ FAIL: Expected to find .limit(12).all()")
        return False

def run_all_tests():
    print("\n🚀 Running WhatsApp Context Retention Tests")
    results = []
    
    results.append(("History Limit", test_conversation_history_limit()))
    results.append(("Database Query", test_database_query_limit()))
    
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
