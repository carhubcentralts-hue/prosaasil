#!/usr/bin/env python3
import os
from flask import Flask

# Simple Flask server for Replit
app = Flask(__name__)

@app.route('/healthz')
def health():
    return 'Hebrew AI CRM Server Running!'

@app.route('/')
def home():
    return '''
    <h1>Hebrew AI Call Center CRM</h1>
    <p>Server is running successfully!</p>
    <p><a href="/healthz">Health Check</a></p>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'🚀 Starting Hebrew AI CRM server on port {port}...')
    app.run(host='0.0.0.0', port=port, debug=False)
