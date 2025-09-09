# server/extensions.py
from flask_seasurf import SeaSurf

csrf = SeaSurf()  # מופע יחיד של SeaSurf לכל האפליקציה - לפי ההנחיות המדויקות