import logging, json, os

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"lvl":record.levelname,"msg":record.getMessage(),"name":record.name}, ensure_ascii=False)

def setup_logging(app):
    h = logging.StreamHandler()
    if os.getenv("FLASK_ENV") == "production":
        h.setFormatter(JsonFormatter())
        app.logger.setLevel(logging.INFO)
    else:
        app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(h)