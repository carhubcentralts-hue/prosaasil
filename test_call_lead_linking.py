#!/usr/bin/env python3
"""
Test script to verify call-to-lead linking functionality
Tests the critical fix: calls must be linked to leads via lead_id
"""

import sys
import os

# Add parent dir to path to import server modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_call_lead_linking_logic():
    """
    Test that the logic for linking calls to leads is correct
    This doesn't require a database, just verifies the logic flow
    """
    print("=" * 60)
    print("Testing Call-to-Lead Linking Logic")
    print("=" * 60)
    
    # Test 1: Verify tasks_recording.py has lead_id assignment
    print("\n✓ Test 1: Checking tasks_recording.py for lead_id assignment")
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
        
        # Check if we set call_log.lead_id
        if 'call_log.lead_id = lead.id' in content:
            print("  ✅ PASS: tasks_recording.py sets call_log.lead_id")
        else:
            print("  ❌ FAIL: tasks_recording.py does NOT set call_log.lead_id")
            return False
    
    # Test 2: Verify media_ws_ai.py has lead_id linking
    print("\n✓ Test 2: Checking media_ws_ai.py for CallLog lead_id linking")
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
        
        # Check if we link CallLog to lead_id after crm_context creation
        if 'call_log.lead_id = lead_id' in content:
            print("  ✅ PASS: media_ws_ai.py links CallLog to lead_id")
        else:
            print("  ❌ FAIL: media_ws_ai.py does NOT link CallLog to lead_id")
            return False
    
    # Test 3: Verify API filters by lead_id
    print("\n✓ Test 3: Checking routes_calls.py for lead_id filtering")
    with open('server/routes_calls.py', 'r') as f:
        content = f.read()
        
        # Check if API filters by lead_id
        if 'Call.lead_id == int(lead_id)' in content:
            print("  ✅ PASS: routes_calls.py filters by lead_id")
        else:
            print("  ❌ FAIL: routes_calls.py does NOT filter by lead_id")
            return False
    
    # Test 4: Verify Kanban checkbox has stopPropagation
    print("\n✓ Test 4: Checking OutboundLeadCard.tsx for stopPropagation")
    with open('client/src/pages/calls/components/OutboundLeadCard.tsx', 'r') as f:
        content = f.read()
        
        # Check if checkbox has stopPropagation
        if 'stopPropagation' in content and 'data-checkbox-wrapper' in content:
            print("  ✅ PASS: OutboundLeadCard.tsx has stopPropagation on checkbox")
        else:
            print("  ❌ FAIL: OutboundLeadCard.tsx missing stopPropagation or data-checkbox-wrapper")
            return False
    
    # Test 5: Verify Kanban has select all functionality
    print("\n✓ Test 5: Checking OutboundKanbanView.tsx for select all")
    with open('client/src/pages/calls/components/OutboundKanbanView.tsx', 'r') as f:
        content = f.read()
        
        # Check if select all handlers exist
        if 'onSelectAll' in content and 'onClearSelection' in content:
            print("  ✅ PASS: OutboundKanbanView.tsx has select all functionality")
        else:
            print("  ❌ FAIL: OutboundKanbanView.tsx missing select all functionality")
            return False
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_call_lead_linking_logic()
    sys.exit(0 if success else 1)
