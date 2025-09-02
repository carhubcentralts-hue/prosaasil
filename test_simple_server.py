#!/usr/bin/env python3

# Simple Flask server without EventLet
from server.app_factory import create_app

app = create_app()

if __name__ == '__main__':
    print('🚀 Starting simple Flask server on port 5000...')
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
