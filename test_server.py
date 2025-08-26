#!/usr/bin/env python3
import os
import sys
import time

# Environment setup
os.environ.update({
    'WS_MODE': 'AI',
    'PUBLIC_BASE_URL': 'https://ai-crmd.replit.app',
    'TWIML_PLAY_GREETING': 'false',
    'FLASK_ENV': 'production'
})

print("🧪 Test Server Starting...")

try:
    # Setup GCP credentials
    creds = os.getenv('GOOGLE_TTS_SA_JSON')
    if creds:
        import tempfile
        temp_path = '/tmp/gcp_creds.json'
        with open(temp_path, 'w') as f:
            f.write(creds)
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_path
        print("🔐 GCP credentials configured")

    # Import and create app
    from server.app_factory import create_app
    print("✅ App factory imported")
    
    app = create_app()
    print("✅ App created")
    
    # Test basic functionality without running
    with app.app_context():
        print(f"✅ App context works")
        print(f"✅ Routes: {len(app.url_map._rules)}")
    
    # Start server with timeout protection
    print("🚀 Starting server...")
    
    from werkzeug.serving import make_server
    server = make_server('0.0.0.0', 5000, app, threaded=True)
    
    # Start in background
    import threading
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    print("✅ Server started successfully!")
    
    # Keep running for 30 seconds
    for i in range(30):
        time.sleep(1)
        if i % 5 == 0:
            print(f"⚡ Server running... {i}/30 seconds")
    
    print("✅ Server test completed!")
    server.shutdown()
    
except Exception as e:
    print(f"❌ Server test error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
