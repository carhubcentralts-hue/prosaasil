import logging
import json
import os

class JsonFormatter(logging.Formatter):
    def format(self, record):
        base = {
            'lvl': record.levelname,
            'msg': record.getMessage(),
            'name': record.name,
        }
        return json.dumps(base, ensure_ascii=False)

def setup_logging(app):
    handler = logging.StreamHandler()
    if os.getenv('FLASK_ENV') == 'production':
        handler.setFormatter(JsonFormatter())
        app.logger.setLevel(logging.INFO)
    else:
        app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(handler)