#!/usr/bin/env python3
"""
Test to verify WhatsApp prompt character limit has been removed.

This test verifies that:
1. WhatsApp prompts are NOT truncated at 3000 characters
2. Full business prompts (up to 20000 chars) are preserved
3. The sanitization function respects the new high max_chars parameter
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_sanitize_text_no_truncation():
    """Test that sanitization with max_length=20000 does NOT truncate prompts"""
    from server.services.prompt_sanitizer import sanitize_prompt_text
    
    # Test 1: Small prompt (should pass through)
    small_prompt = "זה פרומפט קטן לבדיקה."
    result = sanitize_prompt_text(small_prompt, max_length=20000)
    assert len(result["sanitized_text"]) == len(small_prompt), \
        f"Small prompt was modified: {len(result['sanitized_text'])} vs {len(small_prompt)}"
    print("✅ Test 1 passed: Small prompt preserved")
    
    # Test 2: Large prompt with 5000 chars (should NOT be truncated)
    large_prompt = "א" * 5000  # 5000 Hebrew chars
    result = sanitize_prompt_text(large_prompt, max_length=20000)
    assert len(result["sanitized_text"]) == 5000, \
        f"5000-char prompt was truncated: {len(result['sanitized_text'])} vs 5000"
    print("✅ Test 2 passed: 5000-char prompt NOT truncated")
    
    # Test 3: Realistic large business prompt (3500 chars)
    realistic_prompt = """
    אתה העוזר הדיגיטלי של העסק שלנו ב-WhatsApp.
    
    מידע על העסק:
    - שם: העסק המדהים שלנו בע"מ
    - שירותים: פיתוח אתרים, ייעוץ, תמיכה טכנית, אחסון ענן
    - שעות פעילות: ראשון-חמישי 9:00-18:00
    - כתובת: רחוב הרצל 123, תל אביב
    
    זרימת שיחה:
    1. קבל את הלקוח בחום בעברית
    2. שאל איך אתה יכול לעזור להם היום
    3. הקשב בעדינות לצרכים שלהם
    4. ספק מידע רלוונטי על השירותים שלנו
    5. אסוף את פרטי הקשר שלהם (שם, טלפון, אימייל)
    6. הצע לתאם שיחת המשך אם צריך
    7. תודה להם ותאמר שלום
    
    כללים חשובים:
    - דבר תמיד בעברית טבעית
    - היה חם ומקצועי
    - לעולם אל תזכיר מתחרים
    - התמקד בצרכי הלקוח
    - שמור על תשובות תמציתיות (1-2 משפטים)
    - שאל שאלה אחת בכל פעם
    - אל תשתמש באימוג'ים יותר מדי
    
    שימוש בשם לקוח:
    - אם שם הלקוח זמין, השתמש בו באופן טבעי
    - אל תשתמש בשם יותר מדי (נשמע מלאכותי)
    - השתמש בשם בברכה ובסיום
    
    תחום העסק:
    - אנחנו מתמחים בפיתוח אתרים
    - אנחנו מציעים שירותי ייעוץ
    - אנחנו מספקים תמיכה שוטפת
    - אנחנו עובדים עם עסקים קטנים ובינוניים
    - יש לנו ניסיון של מעל 10 שנים בתחום
    
    שירותים מפורטים:
    1. פיתוח אתרים:
       - אתרי WordPress
       - אתרי React/Vue
       - אתרי סחר אלקטרוני
       - אתרי תדמית
    
    2. שירותי ייעוץ:
       - אסטרטגיה דיגיטלית
       - אופטימיזציה לSEO
       - שיווק דיגיטלי
       - אנליטיקס ומדדים
    
    3. תמיכה טכנית:
       - תמיכה 24/7
       - עדכוני אבטחה
       - גיבויים אוטומטיים
       - ניטור זמינות
    
    מחירים:
    - אתר בסיסי: מ-5,000 ש"ח
    - אתר מתקדם: מ-15,000 ש"ח
    - חבילת תמיכה חודשית: מ-500 ש"ח
    - ייעוץ לשעה: 300 ש"ח
    
    תהליך עבודה:
    1. פגישת היכרות ראשונית (חינם)
    2. הצעת מחיר מפורטת
    3. חתימה על חוזה
    4. פיתוח בשלבים
    5. בדיקות והתאמות
    6. השקה
    7. הדרכה ותמיכה
    
    שאלות נפוצות:
    - כמה זמן לוקח לבנות אתר? 4-8 שבועות בממוצע
    - האם אתם מספקים אחסון? כן, כולל בחבילה
    - האם יש אחריות? כן, שנה מלאה
    - האם אפשר לשלם בתשלומים? כן, עד 6 תשלומים ללא ריבית
    
    דוגמאות שיחה:
    
    לקוח: "שלום, אני מעוניין באתר לעסק שלי"
    עוזר: "שלום! נעים מאוד. איזה סוג עסק יש לך?"
    
    לקוח: "יש לי חנות בגדים"
    עוזר: "מעולה! האם אתה מחפש אתר תדמית או סחר אלקטרוני עם קניות אונליין?"
    
    לקוח: "כמה זה עולה?"
    עוזר: "זה תלוי במה שאתה צריך. אתר בסיסי מתחיל מ-5,000 ש"ח, ואתר סחר מ-15,000 ש"ח. רוצה לתאם שיחה לפירוט?"
    
    הערות נוספות:
    - תמיד היה סבלני ונעים
    - אם הלקוח כועס, התנצל והציע פתרון
    - אם אין לך תשובה, הבטח לברר ולחזור אליו
    - תמיד סיים בשאלה כדי לשמור על השיחה פעילה
    - אל תדחוף מכירה - תן ללקוח להחליט
    
    זכור: אתה מייצג את החברה ואתה הפנים של העסק!
    תהיה מקצועי, נעים, ועוזר באמת.
    """ * 2  # Double it to make it ~3500 chars
    
    result = sanitize_prompt_text(realistic_prompt, max_length=20000)
    
    # Should NOT be truncated if under 20000
    # Allow more reduction for whitespace normalization and duplicate space removal (up to 20%)
    min_expected_len = len(realistic_prompt) * 0.80
    assert len(result["sanitized_text"]) >= min_expected_len, \
        f"Realistic prompt was over-truncated: {len(result['sanitized_text'])} vs {len(realistic_prompt)} (min expected: {min_expected_len})"
    # More importantly: ensure it's NOT cut at 3000
    assert len(result["sanitized_text"]) > 3000, \
        f"Prompt was truncated at old 3000 limit! Got: {len(result['sanitized_text'])}"
    print(f"✅ Test 3 passed: Large realistic prompt preserved ({len(result['sanitized_text'])} chars, original: {len(realistic_prompt)} chars)")
    
    # Test 4: Very large prompt at 8000 chars (should still NOT be truncated with 20000 limit)
    very_large_prompt = "ב" * 8000
    result = sanitize_prompt_text(very_large_prompt, max_length=20000)
    assert len(result["sanitized_text"]) == 8000, \
        f"8000-char prompt was truncated: {len(result['sanitized_text'])} vs 8000"
    print("✅ Test 4 passed: 8000-char prompt NOT truncated")
    
    # Test 5: Extremely large prompt at 25000 chars (SHOULD be truncated to ~20000)
    extremely_large_prompt = "ג" * 25000
    result = sanitize_prompt_text(extremely_large_prompt, max_length=20000)
    # Allow a few extra chars for the "..." suffix
    assert len(result["sanitized_text"]) <= 20010, \
        f"25000-char prompt not truncated properly: {len(result['sanitized_text'])}"
    print(f"✅ Test 5 passed: 25000-char prompt truncated to {len(result['sanitized_text'])} (as expected)")


def test_ai_service_uses_high_limit():
    """Verify that ai_service.py uses the new high limit"""
    import ast
    
    # Read the ai_service.py file
    ai_service_path = os.path.join(
        os.path.dirname(__file__),
        'server',
        'services',
        'ai_service.py'
    )
    
    with open(ai_service_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that max_length=20000 is used (not 3000)
    assert 'max_length=20000' in content, \
        "ai_service.py should use max_length=20000 for sanitize_prompt_text"
    
    # Check that the old 3000 limit is NOT used
    assert 'max_length=3000' not in content, \
        "ai_service.py should NOT have the old max_length=3000"
    
    print("✅ Test 6 passed: ai_service.py uses max_length=20000")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing WhatsApp Prompt Character Limit Removal")
    print("=" * 70)
    print()
    
    try:
        test_sanitize_text_no_truncation()
        print()
        test_ai_service_uses_high_limit()
        
        print()
        print("=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("Summary:")
        print("1. ✅ Full business prompts (up to 20000 chars) are preserved")
        print("2. ✅ No truncation at 3000 chars")
        print("3. ✅ Sanitization respects the new max_chars parameter")
        print("4. ✅ ai_service.py updated to use max_length=20000")
        print("5. ✅ WhatsApp prompts will now work with full content")
        print()
        
    except AssertionError as e:
        print()
        print("=" * 70)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 70)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)
