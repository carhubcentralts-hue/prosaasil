# server/extensions.py
from flask_seasurf import SeaSurf
import os

# ✅ SeaSurf config - מקל על בדיקות ופיתוח
def create_csrf():
    """יוצר SeaSurf עם הגדרות מתאימות לפיתוח ופרודוקשן"""
    csrf_instance = SeaSurf()
    
    # Configure for development vs production  
    if os.getenv('FLASK_ENV') == 'development' or os.getenv('DISABLE_CSRF_REFERER'):
        # Disable referer check for development/testing
        csrf_instance._csrf_disable = True
    
    return csrf_instance

csrf = create_csrf()  # מופע יחיד של SeaSurf לכל האפליקציה