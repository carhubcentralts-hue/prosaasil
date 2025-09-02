from flask import Flask
app = Flask(__name__)

@app.route('/healthz')
def health():
    return 'OK'

if __name__ == '__main__':
    print('🚀 Starting basic health server...')
    app.run(host='0.0.0.0', port=5000, debug=False)
