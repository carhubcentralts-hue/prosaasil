import logging

def setup_logging(app):
    if not app.debug:
        logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)