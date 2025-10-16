"""
Hebrew SSML Builder - Smart pronunciation & grammar for Google TTS
Implements professional Hebrew speech synthesis with proper diction
"""
import os
import re
import hashlib
from typing import Dict, Optional

# ✅ Domain Lexicon - תיקוני הגיה למונחים נפוצים
DOMAIN_LEXICON: Dict[str, str] = {
    # ראשי תיבות טכניים
    "CRM": '<say-as interpret-as="characters">C R M</say-as>',
    "AI": "איי איי",
    "API": '<say-as interpret-as="characters">A P I</say-as>',
    "SMS": '<say-as interpret-as="characters">S M S</say-as>',
    "B2B": "בי-טו-בי",
    "B2C": "בי-טו-סי",
    "CEO": '<say-as interpret-as="characters">C E O</say-as>',
    "ROI": '<say-as interpret-as="characters">R O I</say-as>',
    
    # ערים ומיקומים נפוצים
    'ראשל"צ': "ראשון לציון",
    'תל אביב': "תל-אביב",
    'פתח תקווה': "פתח-תקווה",
    'ירושלים': "ירו-שלים",
    
    # מונחי נדל"ן
    "דירת גן": "דירת-גן",
    "פנטהאוז": "פנט-האוז",
    "דופלקס": "דו-פלקס",
    "מ\"ר": "מטר רבוע",
    "חד\"ש": "חדר-שינה",
    
    # ✅ FIX: תיקוני הגייה עבריים נפוצים (ניקוד/דגש)
    "מעולה": "מְעֻלֶּה",  # ניקוד מלא
    "נהדר": "נֶהְדָּר",
    "מצוין": "מְצֻיָּן",
    "בהחלט": "בְּהֶחְלֵט",
    "בוודאי": "בְּוַדַּאי",
    "בסדר": "בְּסֵדֶר",
    "אפשר": "אֶפְשָׁר",
    "בבקשה": "בְּבַקָּשָׁה",
    "תודה": "תּוֹדָה",
    "שלום": "שָׁלוֹם",
    
    # מספרים מיוחדים (אם צריך איות מיוחד)
    "03-": "אפס שלוש מקף",
    "02-": "אפס שתיים מקף",
    "04-": "אפס ארבע מקף",
}

# ✅ Punctuation patterns - תבניות לשיפור פיסוק
PUNCTUATION_RULES = [
    # הוספת פסיק אחרי מילות מעבר
    (r'\b(אז|כן|לא|אוקיי|טוב|נכון)\s', r'\1, '),
    # הוספת נקודה בסוף משפט חסר
    (r'([א-ת])\s*$', r'\1.'),
    # ניקוי "אה", "אממ"
    (r'\bאה+\b', '...'),
    (r'\bאממ+\b', '...'),
    (r'\bהממ+\b', '...'),
]


class HebrewSSMLBuilder:
    """בונה SSML חכם לעברית עם תיקוני הגיה ודקדוק"""
    
    def __init__(self, enable_ssml: bool = True, custom_lexicon: Optional[Dict[str, str]] = None):
        """
        Args:
            enable_ssml: האם להפעיל SSML (או להחזיר טקסט רגיל)
            custom_lexicon: מילון נוסף ספציפי לעסק
        """
        self.enabled = enable_ssml
        self.lexicon = {**DOMAIN_LEXICON}
        if custom_lexicon:
            self.lexicon.update(custom_lexicon)
    
    def normalize_hebrew_text(self, text: str) -> str:
        """נירמול בסיסי - מספרי טלפון, תאריכים"""
        if not text:
            return ""
        
        # ✅ זיהוי מספרי טלפון - כולל +, (), מקפים, רווחים
        # תומך: +972-50-123-4567, (03)1234567, 03-1234567, 0501234567
        def format_phone_number(match):
            number = match.group(0).strip()
            # השתמש ב-say-as telephone לביטוי נכון
            return f'<say-as interpret-as="telephone">{number}</say-as>'
        
        # מספרי טלפון: 7+ תווים מספריים (עם או בלי +, (), -, רווחים)
        # חייב להיות לפחות 7 ספרות בפועל
        phone_pattern = r'(?:[\+\(])?[\d\-\s\(\)]{7,}(?:\))?'
        
        # בדוק שיש לפחות 7 ספרות בפועל
        def check_and_format(match):
            text = match.group(0)
            digit_count = sum(c.isdigit() for c in text)
            if digit_count >= 7:
                return format_phone_number(match)
            return text  # לא מספיק ספרות - השאר כמו שזה
        
        text = re.sub(phone_pattern, check_and_format, text)
        
        # ✅ FIX: המרת מספרים - תומך עד מיליארדים (לא רק 1-3 ספרות!)
        # תופס מספרים עם או בלי פסיקים: 1,960,000 או 1960000
        text = re.sub(r'\b(\d{1,3}(?:,\d{3})*|\d+)\b', self._number_to_hebrew, text)
        
        return text
    
    def _convert_number_to_hebrew(self, num: int) -> str:
        """המרת מספר שלם לעברית - פונקציה רקורסיבית"""
        # מספרים 1-20
        small_numbers = {
            1: 'אחד', 2: 'שניים', 3: 'שלושה', 4: 'ארבעה', 5: 'חמישה',
            6: 'שישה', 7: 'שבעה', 8: 'שמונה', 9: 'תשעה', 10: 'עשרה',
            11: 'אחד עשרה', 12: 'שנים עשרה', 13: 'שלושה עשרה', 
            14: 'ארבעה עשרה', 15: 'חמישה עשרה', 16: 'שישה עשרה',
            17: 'שבעה עשרה', 18: 'שמונה עשרה', 19: 'תשעה עשרה', 20: 'עשרים'
        }
        
        tens_map = {20: 'עשרים', 30: 'שלושים', 40: 'ארבעים', 50: 'חמישים',
                   60: 'שישים', 70: 'שבעים', 80: 'שמונים', 90: 'תשעים'}
        
        hundreds_map = {100: 'מאה', 200: 'מאתיים', 300: 'שלוש מאות', 400: 'ארבע מאות',
                       500: 'חמש מאות', 600: 'שש מאות', 700: 'שבע מאות', 
                       800: 'שמונה מאות', 900: 'תשע מאות'}
        
        # 1-20
        if num in small_numbers:
            return small_numbers[num]
        
        # 21-99
        elif num < 100:
            tens = num // 10 * 10
            ones = num % 10
            if ones == 0:
                return tens_map.get(tens, str(num))
            else:
                return f"{tens_map.get(tens, '')} ו{small_numbers.get(ones, '')}"
        
        # 100-999
        elif num < 1000:
            hundreds = (num // 100) * 100
            remainder = num % 100
            result = hundreds_map.get(hundreds, '')
            
            if remainder > 0:
                # ✅ FIX: "ו" רק אם זה מספר עצמאי, לא חלק ממיליון/אלף
                # context: האם זה נקרא רקורסיבית כחלק ממספר גדול יותר
                # במקרה של 960,000: תשע מאות ששים (בלי "ו")
                # במקרה של 960: תשע מאות ושישים (עם "ו")
                result += f" {self._convert_number_to_hebrew(remainder)}"
            
            return result
        
        # 1,000-999,999 (אלפים) - ✅ סמיכות נכונה!
        elif num < 1_000_000:
            thousands = num // 1000
            remainder = num % 1000
            
            # סמיכות עבריתית נכונה
            if thousands == 1:
                result = "אלף"
            elif thousands == 2:
                result = "אלפיים"
            elif thousands == 3:
                result = "שלושת אלפים"
            elif thousands == 4:
                result = "ארבעת אלפים"
            elif thousands == 5:
                result = "חמשת אלפים"
            elif thousands == 6:
                result = "שישת אלפים"
            elif thousands == 7:
                result = "שבעת אלפים"
            elif thousands == 8:
                result = "שמונת אלפים"
            elif thousands == 9:
                result = "תשעת אלפים"
            elif thousands == 10:
                result = "עשרת אלפים"
            else:
                # מעל 10 אלף - שימוש בצורה רגילה
                result = f"{self._convert_number_to_hebrew(thousands)} אלף"
            
            if remainder > 0:
                # בלי "ו" אם זה מיליון+אלפים (למשל: מיליון תשע מאות ששים אלף)
                # עם "ו" אם זה רק אלפים+מאות (למשל: שלושת אלפים ומאה)
                if thousands >= 1000:  # חלק ממיליון
                    result += f" {self._convert_number_to_hebrew(remainder)}"
                else:
                    result += f" ו{self._convert_number_to_hebrew(remainder)}"
            
            return result
        
        # 1,000,000+ (מיליונים) - ✅ סמיכות נכונה!
        elif num < 1_000_000_000:
            millions = num // 1_000_000
            remainder = num % 1_000_000
            
            # סמיכות עבריתית נכונה
            if millions == 1:
                result = "מיליון"
            elif millions == 2:
                result = "שני מיליון"
            else:
                result = f"{self._convert_number_to_hebrew(millions)} מיליון"
            
            if remainder > 0:
                # בלי "ו" בין מיליון לאלפים (מיליון תשע מאות ששים אלף)
                result += f" {self._convert_number_to_hebrew(remainder)}"
            
            return result
        
        else:
            # מספרים גדולים מאוד - השתמש ב-SSML cardinal
            return f'<say-as interpret-as="cardinal">{num}</say-as>'
    
    def _number_to_hebrew(self, match) -> str:
        """Wrapper לקריאה מ-regex match"""
        num_str = match.group(0)
        try:
            num = int(num_str.replace(',', ''))
            return self._convert_number_to_hebrew(num)
        except:
            return num_str
    
    def _digit_to_hebrew(self, match) -> str:
        """המרת ספרה בודדת לעברית"""
        digit_map = {
            '0': 'אפס', '1': 'אחת', '2': 'שתיים', '3': 'שלוש', 
            '4': 'ארבע', '5': 'חמש', '6': 'שש', '7': 'שבע', 
            '8': 'שמונה', '9': 'תשע'
        }
        return digit_map.get(match.group(0), match.group(0))
    
    def apply_domain_lexicon(self, text: str) -> str:
        """החלפת מונחים לפי מילון הגיה"""
        result = text
        for term, replacement in self.lexicon.items():
            # Case-insensitive replacement with word boundaries
            pattern = rf'\b{re.escape(term)}\b'
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result
    
    def add_micro_breaks(self, text: str) -> str:
        """הוספת הפסקות קצרות לפני מספרים ושמות"""
        # לפני מספר טלפון (מזוהה ע"י ספרות רצופות)
        text = re.sub(r'(\d{2,})', r'<break time="120ms"/>\1', text)
        
        # לפני שמות פרטיים (מילה מתחילה באות גדולה באמצע משפט)
        # text = re.sub(r'(?<!^)(?<!\. )([A-Z][a-z]+)', r'<break time="80ms"/>\1', text)
        
        return text
    
    def restore_punctuation(self, text: str) -> str:
        """שיפור פיסוק אוטומטי"""
        result = text
        for pattern, replacement in PUNCTUATION_RULES:
            result = re.sub(pattern, replacement, result)
        return result
    
    def handle_acronyms(self, text: str) -> str:
        """טיפול בראשי תיבות באנגלית - איות אות-אות"""
        # זיהוי ראשי תיבות (2-5 אותיות גדולות)
        def spell_acronym(match):
            acronym = match.group(0)
            if acronym in self.lexicon:
                return self.lexicon[acronym]
            # איות ברירת מחדל
            letters = ' '.join(list(acronym))
            return f'<say-as interpret-as="characters">{letters}</say-as>'
        
        text = re.sub(r'\b[A-Z]{2,5}\b', spell_acronym, text)
        return text
    
    def build_ssml(self, text: str) -> str:
        """בניית SSML מלא מטקסט עברי"""
        if not self.enabled:
            return text
        
        if not text or not text.strip():
            return ""
        
        # 1. נירמול טקסט
        t = self.normalize_hebrew_text(text)
        
        # 2. שיפור פיסוק
        t = self.restore_punctuation(t)
        
        # 3. טיפול בראשי תיבות
        t = self.handle_acronyms(t)
        
        # 4. מילון הגיה
        t = self.apply_domain_lexicon(t)
        
        # 5. הפסקות מיקרו
        t = self.add_micro_breaks(t)
        
        # 6. עטיפה ב-<speak>
        ssml = f"<speak>{t}</speak>"
        
        return ssml
    
    def get_text_hash(self, text: str) -> str:
        """Hash לטקסט - לצורך caching"""
        return hashlib.md5(text.encode()).hexdigest()[:12]


class NamePronunciationHelper:
    """עוזר לאיות נכון של שמות פרטיים"""
    
    @staticmethod
    def add_hyphenation(name: str) -> str:
        """פירוק שם להברות עם מקפים"""
        # פשוט מאוד - הוספת מקף כל 2-3 תווים
        if len(name) <= 4:
            return name
        
        # דוגמה פשוטה: "רוזנבלום" -> "רו-זנ-בלום"
        parts = []
        i = 0
        while i < len(name):
            chunk_size = 2 if i + 2 < len(name) else len(name) - i
            parts.append(name[i:i+chunk_size])
            i += chunk_size
        
        return '-'.join(parts)
    
    @staticmethod
    def spell_hebrew(name: str) -> str:
        """איות תו-תו בעברית"""
        # "רוזנבלום" -> "ר ו ז נ ב ל ו ם"
        return ' '.join(list(name))
    
    @staticmethod
    def pronounce_name(name: str, confidence: float = 1.0) -> str:
        """
        החלטה איך לבטא שם לפי רמת הביטחון
        
        Args:
            name: השם לביטוי
            confidence: רמת ביטחון (0-1) מה-NER/STT
        
        Returns:
            SSML/טקסט מתוקן
        """
        if confidence >= 0.6:
            # ביטחון גבוה - השאר כמו שהוא
            return name
        
        # ביטחון נמוך - נסה פירוק פונטי
        hyphenated = NamePronunciationHelper.add_hyphenation(name)
        
        # אם עדיין לא נשמע טוב, אייתו
        if confidence < 0.3:
            spelled = NamePronunciationHelper.spell_hebrew(name)
            return f'<say-as interpret-as="characters">{spelled}</say-as>'
        
        return hyphenated


# ✅ Singleton instance
_ssml_builder: Optional[HebrewSSMLBuilder] = None

def get_ssml_builder(enable_ssml: bool = True) -> HebrewSSMLBuilder:
    """קבלת instance גלובלי של SSML Builder"""
    global _ssml_builder
    
    # בדיקת ENV flag
    enable_from_env = os.getenv("ENABLE_TTS_SSML_BUILDER", "true").lower() == "true"
    enabled = enable_ssml and enable_from_env
    
    if _ssml_builder is None or _ssml_builder.enabled != enabled:
        _ssml_builder = HebrewSSMLBuilder(enable_ssml=enabled)
    
    return _ssml_builder
