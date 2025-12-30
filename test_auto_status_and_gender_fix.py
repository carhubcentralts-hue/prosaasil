#!/usr/bin/env python3
"""
Test suite for auto-status and gender fixes
Tests both the status update and gender detection/save functionality
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_gender_field_in_model():
    """Test that gender field exists in Lead model"""
    print("\n" + "="*60)
    print("TEST 1: Gender field in Lead model")
    print("="*60)
    
    try:
        # Read the models file
        with open('server/models_sql.py', 'r') as f:
            content = f.read()
        
        # Check for gender field
        if 'gender = db.Column' in content:
            print("✅ Gender field exists in Lead model")
            if "'male', 'female'" in content:
                print("✅ Gender field has correct values documented")
            return True
        else:
            print("❌ Gender field NOT found in Lead model")
            return False
    except Exception as e:
        print(f"❌ Error checking model: {e}")
        return False

def test_gender_in_updateable_fields():
    """Test that gender is in updateable_fields in routes_leads.py"""
    print("\n" + "="*60)
    print("TEST 2: Gender in API updateable_fields")
    print("="*60)
    
    try:
        with open('server/routes_leads.py', 'r') as f:
            content = f.read()
        
        # Find updateable_fields line
        if "updateable_fields = [" in content:
            # Find the line and check if gender is there
            start = content.find("updateable_fields = [")
            end = content.find("]", start)
            updateable_section = content[start:end+1]
            
            if "'gender'" in updateable_section or '"gender"' in updateable_section:
                print("✅ Gender is in updateable_fields")
                print(f"   Found in: {updateable_section[:100]}...")
                return True
            else:
                print("❌ Gender NOT in updateable_fields")
                print(f"   Current fields: {updateable_section}")
                return False
        else:
            print("❌ updateable_fields not found in routes_leads.py")
            return False
    except Exception as e:
        print(f"❌ Error checking routes: {e}")
        return False

def test_gender_in_api_responses():
    """Test that gender is returned in API responses"""
    print("\n" + "="*60)
    print("TEST 3: Gender in API responses")
    print("="*60)
    
    try:
        with open('server/routes_leads.py', 'r') as f:
            content = f.read()
        
        # Check list_leads
        list_leads_start = content.find('def list_leads():')
        list_leads_end = content.find('def ', list_leads_start + 1)
        list_leads_section = content[list_leads_start:list_leads_end]
        
        has_gender_in_list = '"gender": lead.gender' in list_leads_section
        
        # Check get_lead_detail
        get_detail_start = content.find('def get_lead_detail(')
        get_detail_end = content.find('def ', get_detail_start + 1)
        get_detail_section = content[get_detail_start:get_detail_end]
        
        has_gender_in_detail = '"gender": lead.gender' in get_detail_section
        
        # Check update_lead
        update_start = content.find('def update_lead(')
        update_end = content.find('def ', update_start + 1)
        update_section = content[update_start:update_end]
        
        has_gender_in_update = '"gender": lead.gender' in update_section
        
        if has_gender_in_list:
            print("✅ Gender returned in list_leads()")
        else:
            print("❌ Gender NOT returned in list_leads()")
        
        if has_gender_in_detail:
            print("✅ Gender returned in get_lead_detail()")
        else:
            print("❌ Gender NOT returned in get_lead_detail()")
        
        if has_gender_in_update:
            print("✅ Gender returned in update_lead()")
        else:
            print("❌ Gender NOT returned in update_lead()")
        
        return has_gender_in_list and has_gender_in_detail and has_gender_in_update
    except Exception as e:
        print(f"❌ Error checking API responses: {e}")
        return False

def test_gender_auto_detection_in_tasks():
    """Test that gender auto-detection is in tasks_recording.py"""
    print("\n" + "="*60)
    print("TEST 4: Gender auto-detection in post-call processing")
    print("="*60)
    
    try:
        with open('server/tasks_recording.py', 'r') as f:
            content = f.read()
        
        checks = {
            'detect_gender_from_conversation imported': 'detect_gender_from_conversation' in content,
            'detect_gender_from_name imported': 'detect_gender_from_name' in content,
            'Gender detection logic exists': 'detected_gender = detect_gender_from_conversation' in content,
            'Gender update logic exists': 'lead.gender = detected_gender' in content,
            'Activity logged for gender': '"gender_updated"' in content or "'gender_updated'" in content,
        }
        
        all_passed = True
        for check_name, result in checks.items():
            if result:
                print(f"✅ {check_name}")
            else:
                print(f"❌ {check_name}")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ Error checking tasks_recording: {e}")
        return False

def test_auto_status_fix():
    """Test that auto-status update is outside the if not lead block"""
    print("\n" + "="*60)
    print("TEST 5: Auto-status fix - runs for ALL leads")
    print("="*60)
    
    try:
        with open('server/tasks_recording.py', 'r') as f:
            lines = f.readlines()
        
        # Find the line with "suggest_lead_status_from_call"
        status_line_num = None
        for i, line in enumerate(lines):
            if 'suggest_lead_status_from_call' in line and 'suggested_status = ' in line:
                status_line_num = i
                break
        
        if not status_line_num:
            print("❌ Auto-status call not found")
            return False
        
        print(f"✅ Found auto-status call at line {status_line_num + 1}")
        
        # Check the indentation - should be inside "if lead and call_log and call_log.business_id:"
        # not inside "if not lead and from_number..."
        
        # Find the nearest conditional block
        indent_spaces = len(lines[status_line_num]) - len(lines[status_line_num].lstrip())
        print(f"   Indentation: {indent_spaces} spaces")
        
        # Look backwards to find the controlling if statement
        for i in range(status_line_num - 1, max(0, status_line_num - 50), -1):
            line = lines[i]
            line_indent = len(line) - len(line.lstrip())
            
            # Found a less-indented if statement
            if line_indent < indent_spaces and 'if ' in line:
                if 'if not lead' in line:
                    print("❌ Auto-status is still inside 'if not lead' block")
                    return False
                elif 'if lead and call_log' in line:
                    print("✅ Auto-status is inside 'if lead and call_log' block (runs for ALL leads)")
                    return True
        
        print("⚠️  Could not determine controlling block")
        return False
        
    except Exception as e:
        print(f"❌ Error checking auto-status fix: {e}")
        return False

def test_gender_migration():
    """Test that gender migration exists"""
    print("\n" + "="*60)
    print("TEST 6: Gender column in database migrations")
    print("="*60)
    
    try:
        with open('server/db_migrate.py', 'r') as f:
            content = f.read()
        
        if 'gender' in content.lower() and 'add column gender' in content.lower():
            print("✅ Gender column migration exists")
            if 'migration 53' in content.lower() or 'migration_53' in content:
                print("✅ Gender migration is Migration 53")
            return True
        else:
            print("❌ Gender migration not found")
            return False
    except Exception as e:
        print(f"❌ Error checking migrations: {e}")
        return False

def test_gender_in_ai_prompt():
    """Test that gender is passed to AI"""
    print("\n" + "="*60)
    print("TEST 7: Gender passed to AI for proper addressing")
    print("="*60)
    
    try:
        with open('server/services/realtime_prompt_builder.py', 'r') as f:
            content = f.read()
        
        checks = {
            'build_name_anchor_message has gender param': 'customer_gender: Optional[str]' in content,
            'Masculine Hebrew forms': 'masculine Hebrew forms' in content.lower() or 'זכר' in content,
            'Feminine Hebrew forms': 'feminine Hebrew forms' in content.lower() or 'נקבה' in content,
            'detect_gender_from_name function': 'def detect_gender_from_name' in content,
            'detect_gender_from_conversation function': 'def detect_gender_from_conversation' in content,
        }
        
        all_passed = True
        for check_name, result in checks.items():
            if result:
                print(f"✅ {check_name}")
            else:
                print(f"❌ {check_name}")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ Error checking AI prompt: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 AUTO-STATUS AND GENDER FIX TEST SUITE")
    print("="*60)
    
    tests = [
        ("Gender field in model", test_gender_field_in_model),
        ("Gender in updateable fields", test_gender_in_updateable_fields),
        ("Gender in API responses", test_gender_in_api_responses),
        ("Gender auto-detection", test_gender_auto_detection_in_tasks),
        ("Auto-status fix", test_auto_status_fix),
        ("Gender migration", test_gender_migration),
        ("Gender in AI prompt", test_gender_in_ai_prompt),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*60)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Both fixes are properly implemented.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
