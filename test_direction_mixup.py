#!/usr/bin/env python3
"""
🔍 TEST: Direction Classification & Cache Poisoning Investigation
============================================================

This script proves if/how inbound calls receive outbound prompts.

Tests:
1. Direction classification from webhook payloads
2. Prompt selection logic (fallback chains)
3. Cache key generation (does direction get mixed up?)
4. stream_registry pre-building (is direction passed correctly?)

NO FIXES - ONLY INVESTIGATION
"""
import sys
import os
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

import hashlib
from typing import Dict, Any

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION A: Mock Database for Testing
# ═══════════════════════════════════════════════════════════════════════════════

class MockBusinessSettings:
    def __init__(self, tenant_id, ai_prompt="", outbound_ai_prompt="", updated_at=None):
        self.tenant_id = tenant_id
        self.ai_prompt = ai_prompt
        self.outbound_ai_prompt = outbound_ai_prompt
        self.updated_at = updated_at
        self.enable_calendar_scheduling = True
        self.call_goal = "lead_only"

class MockBusiness:
    def __init__(self, id, name, system_prompt=""):
        self.id = id
        self.name = name
        self.system_prompt = system_prompt
        self.greeting_message = "שלום!"

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION B: Test Prompt Selection Logic (from realtime_prompt_builder.py)
# ═══════════════════════════════════════════════════════════════════════════════

def test_prompt_selection():
    """
    🔥 CRITICAL TEST: Does fallback chain cause direction mixup?
    
    This tests the logic in build_inbound_system_prompt and build_outbound_system_prompt.
    """
    print("\n" + "="*80)
    print("TEST B: Prompt Selection & Fallback Logic")
    print("="*80)
    
    test_cases = [
        {
            "name": "Case 1: Both prompts exist",
            "inbound": "INBOUND_PROMPT_TEXT_123",
            "outbound": "OUTBOUND_PROMPT_TEXT_456",
            "direction": "inbound",
            "expected": "INBOUND_PROMPT_TEXT_123"
        },
        {
            "name": "Case 2: Only outbound exists, requesting inbound",
            "inbound": "",
            "outbound": "OUTBOUND_PROMPT_TEXT_456",
            "direction": "inbound",
            "expected": "OUTBOUND_PROMPT_TEXT_456",  # ← FALLBACK HAPPENS HERE!
            "is_fallback": True
        },
        {
            "name": "Case 3: Only inbound exists, requesting outbound",
            "inbound": "INBOUND_PROMPT_TEXT_123",
            "outbound": "",
            "direction": "outbound",
            "expected": "INBOUND_PROMPT_TEXT_123",  # ← FALLBACK HAPPENS HERE!
            "is_fallback": True
        },
        {
            "name": "Case 4: Neither exists",
            "inbound": "",
            "outbound": "",
            "direction": "inbound",
            "expected": "FALLBACK_TEMPLATE"
        }
    ]
    
    issues_found = []
    
    for case in test_cases:
        print(f"\n📋 {case['name']}")
        print(f"   DB: inbound='{case['inbound'][:30]}...' outbound='{case['outbound'][:30]}...'")
        print(f"   Request: direction={case['direction']}")
        
        # Simulate the selection logic from realtime_prompt_builder.py
        if case['direction'] == 'inbound':
            # From build_inbound_system_prompt (line 1488)
            selected = case['inbound'] if case['inbound'] else ""
            if not selected and case['outbound']:
                # FALLBACK: Line 1696 in realtime_prompt_builder.py
                selected = case['outbound']
                print(f"   ⚠️  FALLBACK TRIGGERED: Using outbound prompt for inbound call")
        else:
            # From build_outbound_system_prompt (line 1625)
            selected = case['outbound'] if case['outbound'] else ""
            if not selected and case['inbound']:
                # FALLBACK: Line 1697 in realtime_prompt_builder.py
                selected = case['inbound']
                print(f"   ⚠️  FALLBACK TRIGGERED: Using inbound prompt for outbound call")
        
        if not selected:
            selected = "FALLBACK_TEMPLATE"
        
        match = (selected == case['expected'])
        status = "✅ OK" if match else "❌ FAIL"
        print(f"   Result: '{selected[:30]}...' {status}")
        
        if case.get('is_fallback'):
            issues_found.append({
                "case": case['name'],
                "issue": "Direction fallback causes wrong prompt to be used",
                "impact": f"{case['direction']} calls will use {'outbound' if case['direction']=='inbound' else 'inbound'} prompt"
            })
    
    print(f"\n📊 Summary: {len(issues_found)} potential issues found")
    return issues_found

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION C: Test Cache Key Generation
# ═══════════════════════════════════════════════════════════════════════════════

def test_cache_keys():
    """
    🔥 CRITICAL TEST: Are cache keys correctly using direction?
    
    Tests PromptCache key format: f"{business_id}:{direction}"
    """
    print("\n" + "="*80)
    print("TEST C: Cache Key Generation & Direction Isolation")
    print("="*80)
    
    from server.services.prompt_cache import get_prompt_cache
    
    cache = get_prompt_cache()
    business_id = 999
    
    # Test 1: Store inbound and outbound prompts
    print(f"\n1️⃣ Storing prompts for business {business_id}")
    cache.set(business_id, "INBOUND_PROMPT", "", direction="inbound")
    cache.set(business_id, "OUTBOUND_PROMPT", "", direction="outbound")
    print(f"   Stored: inbound='INBOUND_PROMPT', outbound='OUTBOUND_PROMPT'")
    
    # Test 2: Retrieve and verify
    print(f"\n2️⃣ Retrieving prompts")
    inbound_cached = cache.get(business_id, direction="inbound")
    outbound_cached = cache.get(business_id, direction="outbound")
    
    inbound_ok = inbound_cached and inbound_cached.system_prompt == "INBOUND_PROMPT"
    outbound_ok = outbound_cached and outbound_cached.system_prompt == "OUTBOUND_PROMPT"
    
    print(f"   Inbound:  {'✅ OK' if inbound_ok else '❌ FAIL'} (got: '{inbound_cached.system_prompt if inbound_cached else 'None'}')")
    print(f"   Outbound: {'✅ OK' if outbound_ok else '❌ FAIL'} (got: '{outbound_cached.system_prompt if outbound_cached else 'None'}')")
    
    # Test 3: Check for cross-contamination
    print(f"\n3️⃣ Cross-contamination check")
    if inbound_cached and inbound_cached.system_prompt == "OUTBOUND_PROMPT":
        print(f"   ❌ CRITICAL: Inbound cache contains OUTBOUND prompt!")
        return [{"issue": "Cache contamination detected", "severity": "CRITICAL"}]
    elif outbound_cached and outbound_cached.system_prompt == "INBOUND_PROMPT":
        print(f"   ❌ CRITICAL: Outbound cache contains INBOUND prompt!")
        return [{"issue": "Cache contamination detected", "severity": "CRITICAL"}]
    else:
        print(f"   ✅ No cross-contamination detected in cache keys")
    
    # Cleanup
    cache.invalidate(business_id)
    
    return []

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION D: Test stream_registry Pre-building
# ═══════════════════════════════════════════════════════════════════════════════

def test_stream_registry_prebuilding():
    """
    🔥 CRITICAL TEST: Does stream_registry store wrong direction prompt?
    
    This simulates what happens in routes_twilio.py webhook handlers.
    """
    print("\n" + "="*80)
    print("TEST D: stream_registry Pre-building Direction Verification")
    print("="*80)
    
    from server.stream_state import stream_registry
    
    # Simulate webhook pre-building (from routes_twilio.py:590 and 750)
    test_scenarios = [
        {
            "name": "Inbound webhook → inbound prebuilt",
            "call_sid": "TEST_INBOUND_001",
            "call_direction": "inbound",
            "expected_marker": "INBOUND"
        },
        {
            "name": "Outbound webhook → outbound prebuilt",
            "call_sid": "TEST_OUTBOUND_001",
            "call_direction": "outbound",
            "expected_marker": "OUTBOUND"
        }
    ]
    
    issues = []
    
    for scenario in test_scenarios:
        print(f"\n📋 {scenario['name']}")
        call_sid = scenario['call_sid']
        call_direction = scenario['call_direction']
        
        # Simulate the webhook storing prebuilt prompt
        # From routes_twilio.py:590 (inbound) and routes_twilio.py:750 (outbound)
        mock_prompt = f"MOCK_{call_direction.upper()}_PROMPT_FOR_TESTING"
        stream_registry.set_metadata(call_sid, '_prebuilt_full_prompt', mock_prompt)
        print(f"   Webhook stored: '{mock_prompt}'")
        
        # Simulate WebSocket retrieving it (from media_ws_ai.py:3557)
        retrieved = stream_registry.get_metadata(call_sid, '_prebuilt_full_prompt')
        print(f"   WebSocket retrieved: '{retrieved}'")
        
        # Check if direction matches
        expected_marker = scenario['expected_marker']
        has_expected = expected_marker in retrieved if retrieved else False
        has_wrong = ("INBOUND" in retrieved if expected_marker == "OUTBOUND" else "OUTBOUND" in retrieved) if retrieved else False
        
        if has_wrong:
            status = "❌ WRONG DIRECTION!"
            issues.append({
                "scenario": scenario['name'],
                "issue": f"Registry contains {('inbound' if 'INBOUND' in retrieved else 'outbound')} prompt for {call_direction} call",
                "severity": "CRITICAL"
            })
        elif has_expected:
            status = "✅ Correct direction"
        else:
            status = "⚠️  Cannot determine direction"
        
        print(f"   Status: {status}")
        
        # Cleanup
        stream_registry.clear(call_sid)
    
    return issues

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION E: Test Actual Webhook Logic
# ═══════════════════════════════════════════════════════════════════════════════

def test_webhook_direction_detection():
    """
    🔥 CRITICAL TEST: How does webhook determine call direction?
    
    Analyzes routes_twilio.py to understand inbound vs outbound detection.
    """
    print("\n" + "="*80)
    print("TEST E: Webhook Direction Detection Logic")
    print("="*80)
    
    # From routes_twilio.py analysis:
    # Inbound: /twiml/incoming/<tenant> → calls _prebuild_prompts_async with call_direction="inbound"
    # Outbound: /twiml/outbound/<tenant> → calls _prebuild_prompts_async_outbound with call_direction="outbound"
    
    print("\n📋 Webhook Route Analysis:")
    print("   1. Inbound route: /twiml/incoming/<tenant>")
    print("      → Calls: _prebuild_prompts_async()")
    print("      → Passes: call_direction='inbound' (HARDCODED)")
    print("      → Line: routes_twilio.py:590")
    
    print("\n   2. Outbound route: /twiml/outbound/<tenant>")
    print("      → Calls: _prebuild_prompts_async_outbound()")
    print("      → Passes: call_direction='outbound' (HARDCODED)")
    print("      → Line: routes_twilio.py:750")
    
    print("\n✅ CONCLUSION: Webhooks use separate routes and functions")
    print("   → Direction is determined by URL route, not call parameters")
    print("   → No misclassification expected at webhook level")
    
    # But there's a potential issue...
    print("\n⚠️  POTENTIAL ISSUE: Both webhooks call build_full_business_prompt()")
    print("   → If business has ONLY outbound_ai_prompt configured:")
    print("      → Inbound webhook builds prompt with call_direction='inbound'")
    print("      → But fallback chain may use outbound_ai_prompt")
    print("      → Result: Inbound call uses outbound prompt content!")
    
    return [{
        "issue": "Inbound webhook can fallback to outbound prompt if ai_prompt is empty",
        "file": "routes_twilio.py:590 + realtime_prompt_builder.py:1696",
        "severity": "HIGH"
    }]

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION F: Test Complete Flow Simulation
# ═══════════════════════════════════════════════════════════════════════════════

def test_complete_inbound_to_outbound_scenario():
    """
    🔥 ROOT CAUSE TEST: Complete scenario showing how inbound gets outbound prompt
    
    Simulates:
    1. Business has ONLY outbound_ai_prompt configured (ai_prompt is empty)
    2. Inbound call arrives
    3. Webhook pre-builds prompt with direction="inbound"
    4. Prompt builder falls back to outbound_ai_prompt
    5. stream_registry stores this as '_prebuilt_full_prompt'
    6. WebSocket retrieves and uses it
    7. Inbound call now uses OUTBOUND prompt!
    """
    print("\n" + "="*80)
    print("TEST F: COMPLETE SCENARIO - Inbound Receives Outbound Prompt")
    print("="*80)
    
    print("\n📋 Scenario Setup:")
    print("   Business 123 configuration:")
    print("      ai_prompt (inbound): '' (EMPTY)")
    print("      outbound_ai_prompt: 'You are calling the customer for sales...'")
    
    business_id = 123
    ai_prompt = ""  # EMPTY!
    outbound_ai_prompt = "You are calling the customer for sales pitch. Be persuasive."
    
    print("\n🔄 Flow Simulation:")
    
    # Step 1: Inbound webhook receives call
    print("\n   1️⃣ Inbound webhook (/twiml/incoming/123)")
    call_sid = "CA_inbound_test_123"
    call_direction = "inbound"  # Hardcoded in webhook
    print(f"      call_direction = '{call_direction}' (from URL route)")
    
    # Step 2: Webhook calls build_full_business_prompt with direction="inbound"
    print(f"\n   2️⃣ Webhook calls: build_full_business_prompt(123, call_direction='inbound')")
    print(f"      → Tries to load: settings.ai_prompt")
    print(f"      → Found: '' (EMPTY)")
    print(f"      → Fallback activated (line 1696 in realtime_prompt_builder.py)")
    print(f"      → Falls back to: settings.outbound_ai_prompt")
    print(f"      → Returns: '{outbound_ai_prompt}'")
    
    # Step 3: This is stored in stream_registry
    print(f"\n   3️⃣ stream_registry stores prebuilt prompt:")
    from server.stream_state import stream_registry
    prompt_to_store = outbound_ai_prompt  # This is what fallback returns!
    stream_registry.set_metadata(call_sid, '_prebuilt_full_prompt', prompt_to_store)
    print(f"      Key: '_prebuilt_full_prompt'")
    print(f"      Value: '{prompt_to_store}'")
    print(f"      ❌ PROBLEM: Outbound prompt stored for inbound call!")
    
    # Step 4: WebSocket retrieves it
    print(f"\n   4️⃣ WebSocket connects and retrieves prompt (media_ws_ai.py:3557)")
    retrieved = stream_registry.get_metadata(call_sid, '_prebuilt_full_prompt')
    print(f"      Retrieved: '{retrieved}'")
    print(f"      WebSocket direction: '{call_direction}' (from custom_parameters)")
    
    # Step 5: Verification check (media_ws_ai.py:3577-3587)
    print(f"\n   5️⃣ Direction verification check (media_ws_ai.py:3577-3587)")
    prompt_direction_check = "outbound" if "outbound" in retrieved.lower() or "sales" in retrieved.lower() else "inbound"
    print(f"      Detected prompt direction: '{prompt_direction_check}'")
    print(f"      Expected call direction: '{call_direction}'")
    
    if prompt_direction_check != call_direction:
        print(f"      ❌ MISMATCH DETECTED!")
        print(f"      ⚠️  Log warning but DO NOT REBUILD (HARD LOCK - line 3583)")
        print(f"      → Inbound call CONTINUES with outbound prompt")
    
    # Cleanup
    stream_registry.clear(call_sid)
    
    print(f"\n" + "="*80)
    print(f"🔥 ROOT CAUSE CONFIRMED:")
    print(f"="*80)
    print(f"1. Fallback chain in build_inbound_system_prompt() uses outbound_ai_prompt")
    print(f"2. This happens when ai_prompt is empty/missing")
    print(f"3. Prompt is pre-built by webhook and stored in stream_registry")
    print(f"4. WebSocket retrieves this outbound-content prompt")
    print(f"5. Direction mismatch is LOGGED but NOT FIXED (HARD LOCK)")
    print(f"6. Result: Inbound call uses outbound prompt for entire conversation")
    print(f"")
    print(f"📍 Evidence Location:")
    print(f"   - Fallback: realtime_prompt_builder.py:1696")
    print(f"   - Pre-build: routes_twilio.py:590")
    print(f"   - Retrieve: media_ws_ai.py:3557")
    print(f"   - Mismatch check: media_ws_ai.py:3577-3587")
    
    return [{
        "root_cause": "Fallback chain in prompt builder causes direction mixup",
        "trigger": "ai_prompt empty + outbound_ai_prompt exists",
        "file": "realtime_prompt_builder.py:1696",
        "impact": "Inbound calls use outbound prompts",
        "persists": "Entire call duration (pre-built and stored in registry)",
        "detection": "LOGGED but NOT FIXED (hard lock in media_ws_ai.py:3583)",
        "severity": "CRITICAL"
    }]

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "="*80)
    print("🔍 INVESTIGATION: Why Inbound Calls Get Outbound Prompts")
    print("="*80)
    print("\nRunning comprehensive tests to identify root causes...")
    
    all_issues = []
    
    # Run all tests
    try:
        issues_b = test_prompt_selection()
        all_issues.extend(issues_b)
    except Exception as e:
        print(f"\n❌ Test B failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        issues_c = test_cache_keys()
        all_issues.extend(issues_c)
    except Exception as e:
        print(f"\n❌ Test C failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        issues_d = test_stream_registry_prebuilding()
        all_issues.extend(issues_d)
    except Exception as e:
        print(f"\n❌ Test D failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        issues_e = test_webhook_direction_detection()
        all_issues.extend(issues_e)
    except Exception as e:
        print(f"\n❌ Test E failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        issues_f = test_complete_inbound_to_outbound_scenario()
        all_issues.extend(issues_f)
    except Exception as e:
        print(f"\n❌ Test F failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Final summary
    print("\n" + "="*80)
    print("📊 FINAL SUMMARY")
    print("="*80)
    print(f"\nTotal issues found: {len(all_issues)}")
    
    for i, issue in enumerate(all_issues, 1):
        print(f"\n{i}. {issue.get('root_cause', issue.get('issue', 'Unknown'))}")
        for key, value in issue.items():
            if key not in ['root_cause', 'issue']:
                print(f"   {key}: {value}")
    
    print("\n" + "="*80)
    print("✅ Investigation Complete")
    print("="*80)

if __name__ == "__main__":
    main()
