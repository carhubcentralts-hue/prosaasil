import eventlet; eventlet.monkey_patch()
from server.app_factory import create_app
app = create_app()
if __name__ == '__main__':
    print('🚀 Starting on port 5000...')
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
