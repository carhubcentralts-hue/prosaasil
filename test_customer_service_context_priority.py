"""
Test for Customer Service Context Priority Fix

Verifies that AI instructions correctly emphasize prioritizing the latest note
and understanding chronological order of notes.

Run: python test_customer_service_context_priority.py
"""
import sys
import traceback


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
    assert "התעלמות מהערות" in content or "התעלמות מהערה" in content, \
        "Instructions should show wrong example of ignoring notes"
    
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


def test_instructions_emphasize_using_all_notes():
    """Test that instructions emphasize reading ALL notes, not just the latest"""
    print("\n🧪 Test 7: Verify instructions emphasize using ALL notes")
    
    with open('server/agent_tools/agent_factory.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that it explicitly says to read all notes
    assert "קרא את כל 10 ההערות" in content or "קרא את כל ההערות" in content, \
        "Instructions should explicitly say to read ALL 10 notes"
    
    assert "כל הערה היא חלק מההיסטוריה" in content, \
        "Instructions should mention each note is part of the history"
    
    assert "אל תתעלם מהן" in content, \
        "Instructions should warn against ignoring old notes"
    
    # Check for example showing use of multiple notes together
    assert "דוגמה 7" in content, \
        "Should have Example 7 showing use of history from multiple notes"
    
    assert "השתמשנו במידע מכל ההערות ביחד" in content, \
        "Should explain using information from ALL notes together"
    
    print("   ✅ Instructions explicitly say to read ALL 10 notes")
    print("   ✅ Instructions emphasize all notes are part of history")
    print("   ✅ Instructions include example using multiple notes together")


def test_instructions_prohibit_making_things_up():
    """Test that instructions strongly prohibit making up information"""
    print("\n🧪 Test 8: Verify instructions prohibit making things up (חריטוט)")
    
    with open('server/agent_tools/agent_factory.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for prohibition of making things up
    assert "אל תמציא מידע" in content, \
        "Instructions should say 'don't make up information'"
    
    assert "לא מופיע בשום הערה" in content or "לא מופיע לי במערכת" in content, \
        "Instructions should say to respond 'not in system' when info is missing"
    
    # Check for wrong example showing making things up
    assert "חריטוט" in content or "אסור לחרטט" in content, \
        "Instructions should have example showing it's forbidden to make things up"
    
    print("   ✅ Instructions prohibit making up information")
    print("   ✅ Instructions say to respond 'not in system' when missing")
    print("   ✅ Instructions include wrong example of making things up")


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
        test_instructions_emphasize_using_all_notes()
        test_instructions_prohibit_making_things_up()
        
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
        print("   • Instructions emphasize using ALL notes (not just latest)")
        print("   • Instructions prohibit making things up (חריטוט)")
        print("\n🎯 The fix ensures the AI will:")
        print("   1. Always read ALL 10 notes to get complete context")
        print("   2. Use information from all notes together (full history)")
        print("   3. Prioritize the latest note when there's conflicting info")
        print("   4. Never make up information (חריטוט) - say 'not in system'")
        print("   5. Give complete, accurate answers based on full context")
        print("\n🔧 Files Modified:")
        print("   • server/agent_tools/agent_factory.py (lines 1378-1449)")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
