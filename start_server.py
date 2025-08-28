#!/usr/bin/env python3
import sys
import os

# Set up environment
sys.path.insert(0, '.')
os.environ['SECRET_KEY'] = 'replit-demo'
os.environ['PYTHONPATH'] = '.'

print("🚀 Starting Hebrew AI Call Center CRM...")

try:
    from server.app_factory import create_app
    app = create_app()
    print("✅ App created successfully!")
    print("🌐 Starting server on 0.0.0.0:5000...")
    print("🔗 Access at: https://workspace-carhubcentralts.replit.app")
    print("🔑 Login: admin@admin.com / admin123")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()