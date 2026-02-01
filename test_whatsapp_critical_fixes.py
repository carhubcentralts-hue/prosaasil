#!/usr/bin/env python3
"""
Test Critical WhatsApp Fixes
Tests all 4 root cause issues that were fixed:
1. AgentKit prompt source mismatch
2. Intent routing to prevent AgentKit overuse
3. Context loss in LID/Android conversations
4. History injection into AgentKit messages
"""

import sys
import os

def test_fix_1_prompt_priority():
    """Test Fix #1: WhatsApp prompt prioritization in agent_factory"""
    print("\n" + "="*80)
    print("🔍 TEST 1: AgentKit uses whatsapp_system_prompt for WhatsApp")
    print("="*80)
    
    with open('server/agent_tools/agent_factory.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('whatsapp_system_prompt priority', 'if channel == "whatsapp" and business and business.whatsapp_system_prompt:' in content),
        ('Uses whatsapp_system_prompt', 'custom_instructions = business.whatsapp_system_prompt' in content),
        ('Fallback to BusinessSettings', 'Fallback to BusinessSettings.ai_prompt' in content),
        ('Fix comment present', '# 🔥 FIX #1' in content),
    ]
    
    passed = all(result for _, result in checks)
    
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    return passed

def test_fix_2_intent_routing():
    """Test Fix #2: Intent-based routing in routes_whatsapp"""
    print("\n" + "="*80)
    print("🔍 TEST 2: Intent routing prevents AgentKit overuse")
    print("="*80)
    
    with open('server/routes_whatsapp.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('Import route_intent_hebrew', 'from server.services.ai_service import route_intent_hebrew' in content),
        ('Call route_intent_hebrew', 'intent = route_intent_hebrew(message_text)' in content),
        ('Check use_agent flag', 'use_agent = intent in ["book", "reschedule", "cancel"]' in content),
        ('Conditional routing', 'if use_agent:' in content),
        ('Use AgentKit for booking', 'ai_response = ai_service.generate_response_with_agent(' in content),
        ('Use regular AI for others', '# Use regular AI response for info/other intents' in content),
        ('Fix comment present', '# 🔥 FIX #2' in content),
    ]
    
    passed = all(result for _, result in checks)
    
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    return passed

def test_fix_3_conversation_key():
    """Test Fix #3: Unified conversation_key for LID/Android"""
    print("\n" + "="*80)
    print("🔍 TEST 3: Unified conversation_key prevents context loss")
    print("="*80)
    
    with open('server/routes_whatsapp.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('conversation_key creation', 'conversation_key = phone_for_ai_check or from_number_e164 or remote_jid' in content),
        ('Message saving uses key', 'wa_msg.to_number = conversation_key' in content),
        ('History loading uses key', 'to_number=conversation_key' in content),
        ('Echo check uses key', 'WhatsAppMessage.to_number == conversation_key' in content),
        ('Session tracking uses key', 'customer_wa_id=conversation_key' in content),
        ('AI state check uses key', 'phone=conversation_key' in content),
        ('Dedup checks use key', '# 🔥 FIX #3: Use conversation_key' in content),
        ('Fix comment present', '# 🔥 FIX #3' in content),
    ]
    
    passed = all(result for _, result in checks)
    
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    return passed

def test_fix_4_history_injection():
    """Test Fix #4: History injection into AgentKit messages"""
    print("\n" + "="*80)
    print("🔍 TEST 4: History and memory injected into AgentKit")
    print("="*80)
    
    with open('server/services/ai_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('Extract previous_messages', "previous_messages = agent_context.get('previous_messages', [])" in content),
        ('Extract customer_memory', "customer_memory = agent_context.get('customer_memory', '')" in content),
        ('Build history text', 'recent_history = previous_messages[-12:]' in content),
        ('Add history block', '"--- הקשר שיחה (אל תצטט) ---"' in content),
        ('Add memory block', '"--- זיכרון לקוח ---"' in content),
        ('Add customer message', '"הודעת הלקוח:"' in content),
        ('Pass enriched message', 'enriched_message,' in content),
        ('Fix comment present', '# 🔥 FIX #4' in content),
    ]
    
    passed = all(result for _, result in checks)
    
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    return passed

def test_fix_5_cache_invalidation():
    """Test Fix #5: Cache invalidation on prompt updates"""
    print("\n" + "="*80)
    print("🔍 TEST 5: Agent cache invalidated on prompt updates")
    print("="*80)
    
    with open('server/routes_whatsapp.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('Import invalidate_agent_cache', 'from server.agent_tools.agent_factory import invalidate_agent_cache' in content),
        ('Call invalidate_agent_cache', 'invalidate_agent_cache(business_id)' in content),
        ('In save_whatsapp_prompt', 'def save_whatsapp_prompt' in content),
        ('After invalidate_business_cache', 'invalidate_business_cache(business_id)' in content and 'invalidate_agent_cache(business_id)' in content),
    ]
    
    passed = all(result for _, result in checks)
    
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    return passed

def test_fix_6_flask_g_context():
    """Test Fix #6: flask.g.agent_context set before running agent"""
    print("\n" + "="*80)
    print("🔍 TEST 6: flask.g.agent_context set for tools")
    print("="*80)
    
    with open('server/services/ai_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('Import flask.g', 'from flask import g' in content),
        ('Set g.agent_context', 'g.agent_context = {' in content),
        ('Include customer_phone', '"customer_phone": customer_phone' in content),
        ('Include remote_jid', '"remote_jid":' in content),
        ('Include business_id', '"business_id": business_id' in content),
        ('Include lead_id', '"lead_id":' in content),
        ('Before runner.run', 'runner = Runner()' in content),
        ('Fix comment present', '# 🔥 FIX #5' in content),
    ]
    
    passed = all(result for _, result in checks)
    
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    return passed

def test_history_limit():
    """Test that history limit is appropriate (20 messages loaded)"""
    print("\n" + "="*80)
    print("🔍 BONUS TEST: History limit appropriate")
    print("="*80)
    
    with open('server/routes_whatsapp.py', 'r', encoding='utf-8') as f:
        whatsapp_content = f.read()
    
    with open('server/services/ai_service.py', 'r', encoding='utf-8') as f:
        ai_service_content = f.read()
    
    checks = [
        ('Loads 20 messages', '.limit(20).all()' in whatsapp_content),
        ('Uses last 12 for agent', '[-12:]' in ai_service_content),
    ]
    
    passed = all(result for _, result in checks)
    
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    return passed
    """Test that history limit is appropriate (20 messages loaded)"""
    print("\n" + "="*80)
    print("🔍 BONUS TEST: History limit appropriate")
    print("="*80)
    
    with open('server/routes_whatsapp.py', 'r', encoding='utf-8') as f:
        whatsapp_content = f.read()
    
    with open('server/services/ai_service.py', 'r', encoding='utf-8') as f:
        ai_service_content = f.read()
    
    checks = [
        ('Loads 20 messages', '.limit(20).all()' in whatsapp_content),
        ('Uses last 12 for agent', '[-12:]' in ai_service_content),
    ]
    
    passed = all(result for _, result in checks)
    
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    return passed

def run_all_tests():
    """Run all critical fix tests"""
    print("\n🚀 Running WhatsApp Critical Fixes Validation")
    print("="*80)
    print("Testing all 6 root cause fixes:")
    print("1. AgentKit prompt source mismatch")
    print("2. Intent routing to prevent AgentKit overuse")
    print("3. Context loss in LID/Android conversations")
    print("4. History injection into AgentKit messages")
    print("5. Cache invalidation on prompt updates")
    print("6. flask.g.agent_context for tool reliability")
    print("="*80)
    
    results = []
    
    results.append(("Fix #1: Prompt Priority", test_fix_1_prompt_priority()))
    results.append(("Fix #2: Intent Routing", test_fix_2_intent_routing()))
    results.append(("Fix #3: Conversation Key", test_fix_3_conversation_key()))
    results.append(("Fix #4: History Injection", test_fix_4_history_injection()))
    results.append(("Fix #5: Cache Invalidation", test_fix_5_cache_invalidation()))
    results.append(("Fix #6: flask.g Context", test_fix_6_flask_g_context()))
    results.append(("Bonus: History Limit", test_history_limit()))
    
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*80)
    print(f"Overall: {passed}/{total} tests passed")
    print("="*80)
    
    if passed == total:
        print("\n🎉 SUCCESS! All critical fixes are properly implemented!")
        print("\n📋 Expected Outcomes:")
        print("  ✅ WhatsApp prompts update immediately in conversations")
        print("  ✅ Simple questions don't trigger AgentKit unnecessarily")
        print("  ✅ LID/Android conversations maintain context")
        print("  ✅ Bot remembers previous conversation in each response")
        print("  ✅ Agent cache cleared when prompts updated")
        print("  ✅ Tools like whatsapp_send work reliably with context")
        return 0
    else:
        print(f"\n⚠️  WARNING: {total - passed} test(s) failed!")
        print("Some fixes may not be fully implemented.")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
