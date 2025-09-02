#!/usr/bin/env python3
import eventlet
eventlet.monkey_patch()

from flask import Flask

app = Flask(__name__)

@app.route('/healthz')
def health():
    return 'MINIMAL OK'

if __name__ == '__main__':
    print('🚀 Starting minimal Flask on port 3000...')
    from eventlet import wsgi
    wsgi.server(eventlet.listen(('0.0.0.0', 3000)), app)
