#!/usr/bin/env python3
import eventlet
eventlet.monkey_patch()

from flask import Flask

app = Flask(__name__)

@app.route('/healthz')
def health():
    return {'status': 'ok', 'msg': 'simple app works'}, 200

if __name__ == '__main__':
    print("Simple test app created")