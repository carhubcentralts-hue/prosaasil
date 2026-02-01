"""
Test improved summary service for call summaries
Verifies that summaries are informative and well-structured
"""
import pytest
from unittest.mock import Mock, patch
from server.services.summary_service import summarize_conversation


def test_wedding_invitation_summary():
    """
    Test summary generation for a wedding invitation call.
    This is based on the real example from the problem statement.
    """
    # The actual transcript from the wedding invitation call
    transcript = """בשעה טובה ומבורכת, אלון ושני שמחים להזמין אותך לחתונה שלהם ורצינו לשאול אם אתה מגיע.

כן, אני מגיע.

הכל בסדר. תודה רבה שהתקנת. שיהיה לך יום מקסים.

מה, אני מגיע, אני מגיע.

ברור, אין בעיה. נשמח אם תעדכן כשתדע. שיהיה יום נהדר.

אני אומר לך שאני מגיע.

איזה כיף, נשמח לדעת. כמה אנשים אתם מגיעים?

ארבעה אנשים.

תודה רבה, רשמתי. החתונה מתקיימת בגן האירועים הוד והדר בדרך הים 18, ראשון לציון. מחכים לראות אתכם.

תודה, ביי."""
    
    # Mock OpenAI response with improved Hebrew summary
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = """שיחה 54 שניות - הושלמה בהצלחה.

נושא: הזמנה לחתונה של אלון ושני.

המארגנים שאלו האם המוזמן מגיע לחתונה. המוזמן אישר הגעה עם ארבעה אנשים.
מיקום: גן האירועים הוד והדר בדרך הים 18, ראשון לציון.

תוצאה: המוזמן אישר הגעה בוודאות.

פעולה נדרשת: המוזמן ביקש לעדכן את מספר המוזמנים הסופי כשיידע בוודאות."""
    
    with patch('server.services.summary_service.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        summary = summarize_conversation(
            transcription=transcript,
            call_sid="test_call_123",
            call_duration=54
        )
        
        # Verify summary is not empty
        assert summary, "Summary should not be empty"
        
        # Verify summary contains key information
        assert "שיחה" in summary or "54" in summary, "Summary should mention call duration"
        assert len(summary.split()) >= 50, "Summary should be substantial (at least 50 words)"
        assert len(summary.split()) <= 150, "Summary should be concise (at most 150 words)"
        
        # Verify the prompt was in Hebrew
        call_args = mock_client.chat.completions.create.call_args
        user_message = call_args[1]['messages'][1]['content']
        assert 'סכם את השיחה' in user_message or 'תמלול השיחה' in user_message, \
            "Prompt should be in Hebrew"


def test_summary_structure():
    """
    Test that the summary follows the improved structure:
    1. Duration + completion status
    2. Topic/purpose
    3. Key details
    4. Outcome
    5. Required action
    """
    transcript = """שלום, זה משרד עורכי דין כהן. התקשרנו בנוגע לתיק שלך.

כן, מה קורה עם התיק?

התיק התקדם והיום יש לנו מועד בבית משפט. האם תוכל להגיע מחר בשעה 10?

כן, אני אגיע.

מצוין, נתראה מחר."""
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = """שיחה 45 שניות - הושלמה בהצלחה.

נושא: עדכון על תיק משפטי.

משרד עו"ד כהן עדכן את הלקוח על התקדמות התיק. יש מועד בבית משפט מחר בשעה 10.

תוצאה: הלקוח אישר הגעה.

פעולה נדרשת: הלקוח יגיע למועד מחר בשעה 10."""
    
    with patch('server.services.summary_service.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        summary = summarize_conversation(
            transcription=transcript,
            call_sid="test_call_456",
            call_duration=45
        )
        
        # Verify summary structure
        assert "שיחה" in summary, "Should start with call duration"
        
        # Check that the prompt requested structured output
        call_args = mock_client.chat.completions.create.call_args
        user_message = call_args[1]['messages'][1]['content']
        
        # Verify Hebrew prompt structure
        assert 'שורה ראשונה' in user_message, "Prompt should specify first line requirement"
        assert 'נושא' in user_message, "Prompt should request topic"
        assert 'פרטים עיקריים' in user_message, "Prompt should request key details"
        assert 'תוצאה' in user_message, "Prompt should request outcome"
        assert 'פעולה נדרשת' in user_message, "Prompt should request required action"


def test_short_call_no_answer():
    """
    Test summary for very short calls (no answer).
    """
    # Very short transcript or no transcript
    transcript = ""
    
    summary = summarize_conversation(
        transcription=transcript,
        call_sid="test_call_789",
        call_duration=0
    )
    
    # Should return a no-answer summary
    assert summary, "Should return a summary even for 0-second calls"
    assert "לא נענתה" in summary or "אין מענה" in summary, \
        "Should indicate no answer"


def test_temperature_is_zero():
    """
    Test that temperature is set to 0 for deterministic summaries.
    """
    transcript = "שיחה קצרה לבדיקה."
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "שיחה 10 שניות - בדיקה."
    
    with patch('server.services.summary_service.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        summarize_conversation(
            transcription=transcript,
            call_sid="test_call_temp",
            call_duration=10
        )
        
        # Verify temperature is 0
        call_args = mock_client.chat.completions.create.call_args
        assert call_args[1]['temperature'] == 0.0, \
            "Temperature should be 0.0 for deterministic summaries"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
