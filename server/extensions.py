# server/extensions.py
from flask_seasurf import SeaSurf

csrf = SeaSurf()  # מופע יחיד של SeaSurf לכל האפליקציה

# NUCLEAR CSRF BYPASS for impersonation
def csrf_impersonate_exempt(endpoint):
    """Completely exempt impersonate endpoints from CSRF"""
    return '/impersonate' in endpoint

# Set up CSRF exemptions
csrf.exempt_urls(csrf_impersonate_exempt)