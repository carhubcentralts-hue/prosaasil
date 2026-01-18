"""
Test for Customer Service Context Priority Fix

Verifies that AI instructions correctly emphasize prioritizing the latest note
and understanding chronological order of notes.

Run: python test_customer_service_context_priority.py
"""


def test_instructions_text_has_priority_guidance():
    """Test that the instructions text includes priority guidance"""
    print("🧪 Test 1: Verify agent_factory.py contains priority guidance")
    
    # Read the agent_factory.py file directly
    with open('server/agent_tools/agent_factory.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for latest note priority
    assert "העדכנית ביותר" in content, \
        "Instructions should mention 'העדכנית ביותר' (latest/most recent)"
    
    assert "הערה עדכנית ביותר - מידע מדויק" in content, \
        "Instructions should mention the marker '[הערה עדכנית ביותר - מידע מדויק]'"
    
    assert "פיסת האמת" in content or "מקור האמת" in content, \
        "Instructions should mention 'source of truth' concept"
    
    print("   ✅ Instructions mention latest note priority")
    print("   ✅ Instructions mention the latest note marker")
    print("   ✅ Instructions mention source of truth concept")


def test_instructions_removed_300_char_truncation():
    """Test that outdated 300-character truncation reference is removed"""
    print("\n🧪 Test 2: Verify 300-char truncation reference is removed")
    
    with open('server/agent_tools/agent_factory.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that old truncation reference is removed
    assert "מקוצרות ל-300 תווים" not in content, \
        "Instructions should NOT mention '300 character truncation'"
    
    # Check that new text mentions full content
    assert "תוכן מלא" in content or "ללא קיצור" in content, \
        "Instructions should mention 'full content' or 'no truncation'"
    
    print("   ✅ Old 300-char truncation reference removed")
    print("   ✅ New 'full content' reference added")


def test_instructions_clarify_notes_ordering():
    """Test that instructions clarify notes are ordered newest to oldest"""
    print("\n🧪 Test 3: Verify instructions clarify notes ordering")
    
    with open('server/agent_tools/agent_factory.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that ordering is mentioned
    assert "ממוינות מהחדשה לישנה" in content or "מהעדכנית לישנה" in content, \
        "Instructions should mention notes are sorted newest to oldest"
    
    assert "הראשונה ברשימה" in content, \
        "Instructions should mention 'first in the list'"
    
    print("   ✅ Instructions clarify notes ordering (newest to oldest)")
    print("   ✅ Instructions explain first note is most recent")


def test_instructions_have_price_change_example():
    """Test that instructions include example of changing prices/info"""
    print("\n🧪 Test 4: Verify instructions include price change example")
    
    with open('server/agent_tools/agent_factory.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for price example (from problem statement)
    assert "מחיר" in content, \
        "Instructions should include price example"
    
    assert "דוגמה 6" in content or "מידע מחיר משתנה" in content, \
        "Instructions should have Example 6 about changing price info"
    
    # Check for the specific wrong example
    assert "התעלמות מהערה עדכנית" in content, \
        "Instructions should show wrong example of ignoring latest note"
    
    # Check for specific numbers from the problem statement
    assert "1500 שקלים" in content and "3000 שקלים" in content, \
        "Instructions should include the specific example from problem statement"
    
    print("   ✅ Instructions include price change example")
    print("   ✅ Instructions show wrong example of ignoring latest note")
    print("   ✅ Instructions include specific numbers from problem statement")


def test_instructions_handle_conflicting_notes():
    """Test that instructions address handling conflicting information"""
    print("\n🧪 Test 5: Verify instructions handle conflicting notes")
    
    with open('server/agent_tools/agent_factory.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for conflict handling
    assert "סתירה בין הערות" in content, \
        "Instructions should mention 'conflict between notes'"
    
    assert "האמן להערה העדכנית" in content or "העדף אותה על פני הערות ישנות" in content, \
        "Instructions should say to trust/prefer the latest note"
    
    print("   ✅ Instructions address handling conflicting information")
    print("   ✅ Instructions specify to trust the latest note")


def test_instructions_emphasize_with_fire_emoji():
    """Test that critical points are emphasized with fire emoji"""
    print("\n🧪 Test 6: Verify critical points are emphasized")
    
    with open('server/agent_tools/agent_factory.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count fire emoji for latest note emphasis
    lines_with_fire_and_latest = [
        line for line in content.split('\n')
        if '🔥🔥' in line and 'העדכנית ביותר' in line
    ]
    
    assert len(lines_with_fire_and_latest) >= 2, \
        f"Should have at least 2 lines with 🔥🔥 emphasizing latest note, found {len(lines_with_fire_and_latest)}"
    
    print(f"   ✅ Found {len(lines_with_fire_and_latest)} lines with 🔥🔥 emphasizing latest note")
    print("   ✅ Critical points are properly emphasized")


if __name__ == "__main__":
    print("=" * 80)
    print("🧪 Testing Customer Service Context Priority Fix")
    print("=" * 80)
    
    try:
        test_instructions_text_has_priority_guidance()
        test_instructions_removed_300_char_truncation()
        test_instructions_clarify_notes_ordering()
        test_instructions_have_price_change_example()
        test_instructions_handle_conflicting_notes()
        test_instructions_emphasize_with_fire_emoji()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print("\n📋 Summary:")
        print("   • Instructions emphasize prioritizing the LATEST note")
        print("   • Outdated 300-char truncation reference removed")
        print("   • Notes ordering (newest→oldest) is clearly explained")
        print("   • Price change example added (matching problem statement)")
        print("   • Conflict handling instructions added (trust latest)")
        print("   • Critical points emphasized with 🔥🔥 emoji")
        print("\n🎯 The fix ensures the AI will:")
        print("   1. Always prioritize the most recent note as source of truth")
        print("   2. Recognize the '[הערה עדכנית ביותר - מידע מדויק]' marker")
        print("   3. Understand notes are ordered newest to oldest")
        print("   4. Handle conflicts by trusting the latest information")
        print("   5. Give correct answers based on the latest context")
        print("\n🔧 Files Modified:")
        print("   • server/agent_tools/agent_factory.py (lines 1378-1449)")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import sys
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
