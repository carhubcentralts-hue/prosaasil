"""
Punctuation Polish for Hebrew STT Output
Enhances punctuation from STT before sending to TTS for natural speech
"""
import re
import os
import logging

log = logging.getLogger("punctuation_polish")


class HebrewPunctuationPolisher:
    """שיפור פיסוק אוטומטי לטקסט עברי מSTT"""
    
    # ✅ כללי פיסוק חכמים
    RULES = [
        # הוספת פסיק אחרי מילות מעבר/אישור
        (r'\b(אז|כן|לא|אוקיי|טוב|נכון|בסדר|מעולה|נהדר)\s+(?=[א-ת])', r'\1, '),
        
        # הוספת נקודה בסוף משפט אם חסר
        (r'([א-ת])$', r'\1.'),
        
        # ניקוי התנהגויות דיבור ("אה", "אממ", "המ")
        (r'\bאה+\b', '...'),
        (r'\bאממ+\b', '...'),
        (r'\bהממ+\b', '...'),
        (r'\bאהה+\b', '...'),
        
        # תיקון רווחים כפולים
        (r'\s{2,}', ' '),
        
        # תיקון נקודות כפולות
        (r'\.{2,}', '...'),
        
        # הוספת רווח אחרי פסיק אם חסר
        (r',(?=\S)', r', '),
        
        # הוספת רווח אחרי נקודה אם חסר
        (r'\.(?=[א-תA-Za-z])', r'. '),
    ]
    
    def __init__(self, enable: bool = True):
        """
        Args:
            enable: האם להפעיל שיפור פיסוק
        """
        self.enabled = enable
        log.info(f"Punctuation Polisher: {'enabled' if enable else 'disabled'}")
    
    def polish(self, text: str) -> str:
        """
        שיפור פיסוק של טקסט מSTT
        
        Args:
            text: טקסט גולמי מה-STT
        
        Returns:
            טקסט משופר עם פיסוק טוב יותר
        """
        if not self.enabled or not text:
            return text
        
        result = text.strip()
        
        # החלת כל הכללים
        for pattern, replacement in self.RULES:
            result = re.sub(pattern, replacement, result)
        
        # ניקוי סופי
        result = result.strip()
        
        # לוג רק אם היה שינוי משמעותי
        if len(result) != len(text) or result != text:
            log.debug(f"Punctuation polished: '{text[:50]}...' → '{result[:50]}...'")
        
        return result
    
    def polish_with_breaks(self, text: str) -> str:
        """
        שיפור פיסוק + הוספת SSML breaks
        
        Returns:
            טקסט עם <break> tags ל-TTS טבעי יותר
        """
        if not self.enabled:
            return text
        
        # קודם שיפור פיסוק רגיל
        result = self.polish(text)
        
        # הוספת breaks אחרי נקודה
        result = re.sub(r'\.(\s+)', r'.<break time="200ms"/>\1', result)
        
        # הוספת breaks קצרים אחרי פסיק
        result = re.sub(r',(\s+)', r',<break time="100ms"/>\1', result)
        
        return result


# ✅ Singleton instance
_polisher = None

def get_punctuation_polisher(enable: bool = True) -> HebrewPunctuationPolisher:
    """קבלת instance גלובלי של Punctuation Polisher"""
    global _polisher
    
    # בדיקת ENV flag
    enable_from_env = os.getenv("ENABLE_HEBREW_GRAMMAR_POLISH", "true").lower() == "true"
    enabled = enable and enable_from_env
    
    if _polisher is None or _polisher.enabled != enabled:
        _polisher = HebrewPunctuationPolisher(enable=enabled)
    
    return _polisher


def polish_hebrew_text(text: str) -> str:
    """Convenience function לשיפור פיסוק"""
    return get_punctuation_polisher().polish(text)
