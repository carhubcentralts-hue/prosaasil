from flask import Flask
import os
import time

os.environ['WS_MODE'] = 'AI'
os.environ['PUBLIC_BASE_URL'] = 'https://ai-crmd.replit.app'

from main import app

@app.route('/test')
def test():
    return f"Server works! Time: {time.time()}"

if __name__ == '__main__':
    print("🚀 Starting simple test server...")
    app.run(host='0.0.0.0', port=5000)
