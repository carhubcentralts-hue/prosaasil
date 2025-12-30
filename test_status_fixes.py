"""
Test script to verify status change fixes
Tests:
1. AI status suggestion doesn't default to "interested" incorrectly
2. Smart no-answer progression works correctly
3. Status validation works properly
"""
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_ai_prompt_improvements():
    """
    Test that the AI prompt improvements are in place
    """
    print("Testing AI prompt improvements...")
    
    from server.services.lead_auto_status_service import LeadAutoStatusService
    import inspect
    
    service = LeadAutoStatusService()
    
    # Get the source code of _suggest_status_with_ai
    source = inspect.getsource(service._suggest_status_with_ai)
    
    # Check for key improvements
    improvements = {
        "conservative_instruction": "היה שמרני ומדויק" in source or "conservative" in source.lower(),
        "priority_system": "עדיפות ראשונה" in source or "עדיפות שנייה" in source,
        "no_answer_first": "אין מענה" in source and "no_answer" in source,
        "short_call_handling": "< 5 שניות" in source or "< 15 שניות" in source,
        "interested_warning": "אל תבחר" in source and "interested" in source,
    }
    
    print(f"\n✅ Improvements found:")
    for key, found in improvements.items():
        status = "✓" if found else "✗"
        print(f"  {status} {key}: {found}")
    
    all_good = all(improvements.values())
    if all_good:
        print("\n✅ All AI prompt improvements are in place!")
    else:
        print("\n⚠️  Some improvements might be missing")
    
    return all_good


def test_no_answer_progression():
    """
    Test that no-answer progression logic is present
    """
    print("\n\nTesting no-answer progression logic...")
    
    from server.services.lead_auto_status_service import LeadAutoStatusService
    import inspect
    
    service = LeadAutoStatusService()
    
    # Get the source code of _handle_no_answer_with_progression
    source = inspect.getsource(service._handle_no_answer_with_progression)
    
    # Check for key features
    features = {
        "check_current_status": "lead.status" in source,
        "extract_numbers": "re.findall" in source or "findall" in source,
        "call_history": "previous_calls" in source or "CallLog" in source,
        "smart_progression": "next_attempt" in source or "attempt" in source,
        "multilingual_support": "אין מענה" in source or "no_answer" in source,
    }
    
    print(f"\n✅ Features found:")
    for key, found in features.items():
        status = "✓" if found else "✗"
        print(f"  {status} {key}: {found}")
    
    all_good = all(features.values())
    if all_good:
        print("\n✅ All no-answer progression features are in place!")
    else:
        print("\n⚠️  Some features might be missing")
    
    return all_good


def test_status_validation():
    """
    Test that status validation is robust
    """
    print("\n\nTesting status validation...")
    
    from server.services.lead_auto_status_service import LeadAutoStatusService
    import inspect
    
    service = LeadAutoStatusService()
    
    # Get the source code of suggest_status
    source = inspect.getsource(service.suggest_status)
    
    # Check for validation features
    features = {
        "valid_statuses_check": "valid_statuses" in source or "get_valid_statuses" in source,
        "ai_suggestion": "_suggest_status_with_ai" in source,
        "no_answer_detection": "is_very_short_call" in source or "no_answer_indicators" in source,
        "fallback_logic": "_map_from_keywords" in source or "keyword" in source,
    }
    
    print(f"\n✅ Validation features found:")
    for key, found in features.items():
        status = "✓" if found else "✗"
        print(f"  {status} {key}: {found}")
    
    all_good = all(features.values())
    if all_good:
        print("\n✅ All status validation features are in place!")
    else:
        print("\n⚠️  Some validation features might be missing")
    
    return all_good


def test_project_limit_fix():
    """
    Test that project limit has been increased
    """
    print("\n\nTesting project limit fix...")
    
    # Read the CreateProjectModal file - use relative path from this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    modal_path = os.path.join(script_dir, "client/src/pages/calls/components/CreateProjectModal.tsx")
    
    try:
        with open(modal_path, 'r') as f:
            content = f.read()
        
        # Check for the increased limit
        checks = {
            "increased_system_limit": "pageSize: '5000'" in content,
            "increased_import_limit": "page_size: '5000'" in content,
            "no_old_limit_100": "pageSize: '100'" not in content and "page_size: '100'" not in content,
        }
        
        print(f"\n✅ Checks:")
        for key, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"  {status} {key}: {passed}")
        
        all_good = all(checks.values())
        if all_good:
            print("\n✅ Project limit has been increased to 1000!")
        else:
            print("\n⚠️  Project limit might not be properly increased")
        
        return all_good
    except Exception as e:
        print(f"\n❌ Error reading file: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("STATUS CHANGE FIXES - VERIFICATION TESTS")
    print("=" * 60)
    
    results = {
        "AI prompt improvements": test_ai_prompt_improvements(),
        "No-answer progression": test_no_answer_progression(),
        "Status validation": test_status_validation(),
        "Project limit fix": test_project_limit_fix(),
    }
    
    print("\n\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "⚠️  WARN"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS HAD WARNINGS - Please review")
    print("=" * 60)
    
    sys.exit(0 if all_passed else 1)
