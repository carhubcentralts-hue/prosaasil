# server/extensions.py
from flask_seasurf import SeaSurf

# תיקון בעיית SeaSurf שגיאה - מאותחל נכון לפי ההנחיות
csrf = SeaSurf()  # מופע יחיד של SeaSurf לכל האפליקציה