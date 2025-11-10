# server/extensions.py
from flask_seasurf import SeaSurf
import os

# ✅ SeaSurf config - מקור יחיד לCSRF (לפי ההנחיות המדויקות)
def create_csrf():
    """יוצר SeaSurf עם הגדרות מתאימות לפיתוח ופרודוקשן - CSRF פעיל תמיד!"""
    csrf_instance = SeaSurf()
    
    # ❌ כבר לא מבטלים CSRF - פעיל תמיד לפי ההנחיות החדשות
    # הפטורים מנוהלים על ידי @csrf.exempt על endpoints ספציפיים
    
    return csrf_instance

csrf = create_csrf()  # מופע יחיד של SeaSurf לכל האפליקציה