#!/usr/bin/env python3
import os
import sys

# Basic environment setup
os.environ.update({
    'WS_MODE': 'AI',
    'PUBLIC_BASE_URL': 'https://ai-crmd.replit.app',
    'TWIML_PLAY_GREETING': 'false'
})

print("🚀 Ultra Simple Server Test")
print("=" * 50)

try:
    print("1. Testing Flask import...")
    from flask import Flask
    print("✅ Flask OK")
    
    print("2. Testing app creation...")
    app = Flask(__name__)
    print("✅ Basic Flask app OK")
    
    print("3. Testing our app_factory...")
    from server.app_factory import create_app
    print("✅ app_factory import OK")
    
    print("4. Creating our app...")
    our_app = create_app()
    print("✅ Our app created OK")
    
    print("5. Starting server...")
    our_app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    
except Exception as e:
    print(f"❌ Error at step: {e}")
    import traceback
    traceback.print_exc()
