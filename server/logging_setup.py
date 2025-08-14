# server/logging_setup.py
import os, sys, uuid, time, logging, logging.config
from logging.handlers import RotatingFileHandler
from flask import g, request

DEFAULT_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT    = os.getenv("LOG_FORMAT", "plain").lower()  # "plain" | "json"
LOG_DIR       = os.getenv("LOG_DIR", "logs")
MAX_BYTES     = int(os.getenv("LOG_MAX_BYTES", 10_000_000))
BACKUPS       = int(os.getenv("LOG_BACKUPS", 5))
SLOW_MS       = int(os.getenv("DB_SLOW_MS", 300))  # slow query threshold

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Try to get request_id from Flask's g object
            from flask import g
            rid = getattr(g, "request_id", "-")
        except (RuntimeError, ImportError):
            # Outside of application context or Flask not available
            rid = "-"
        setattr(record, "request_id", rid)
        return True

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _build_handlers(json_enabled: bool):
    base_fmt = '%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s'
    if json_enabled:
        try:
            from pythonjsonlogger import jsonlogger
            formatter = jsonlogger.JsonFormatter(
                '%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s'
            )
        except Exception:
            formatter = logging.Formatter(base_fmt)
    else:
        formatter = logging.Formatter(base_fmt)

    req_filter = RequestIdFilter()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(DEFAULT_LEVEL)
    console.setFormatter(formatter)
    console.addFilter(req_filter)

    _ensure_dir(LOG_DIR)
    app_file = RotatingFileHandler(os.path.join(LOG_DIR, "app.log"),
                                   maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
    app_file.setLevel(DEFAULT_LEVEL)
    app_file.setFormatter(formatter)
    app_file.addFilter(req_filter)

    err_file = RotatingFileHandler(os.path.join(LOG_DIR, "error.log"),
                                   maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
    err_file.setLevel(logging.ERROR)
    err_file.setFormatter(formatter)
    err_file.addFilter(req_filter)

    return [console, app_file, err_file]

def init_logging(app=None):
    json_enabled = LOG_FORMAT == "json"
    handlers = _build_handlers(json_enabled)
    root = logging.getLogger()
    root.setLevel(DEFAULT_LEVEL)
    # reset handlers to avoid duplicates in dev reload
    root.handlers = []
    for h in handlers:
        root.addHandler(h)

    # quieter noisy libs
    logging.getLogger("werkzeug").setLevel(os.getenv("LOG_WERKZEUG", "WARNING"))
    logging.getLogger("urllib3").setLevel("WARNING")

    # Use a simple logger that doesn't require Flask context for initialization
    print("✅ Professional logging system initialized with Request-ID tracking")

def _mask_phone(s: str) -> str:
    if not s: return s
    digits = ''.join([c for c in s if c.isdigit()])
    if len(digits) < 6: return s
    return s[:2] + "****" + s[-2:]

def install_request_hooks(app):
    import traceback
    log = logging.getLogger("request")

    @app.before_request
    def _before():
        # correlate by header OR Twilio CallSid/WhatsApp MessageSid OR random
        rid = (request.headers.get("X-Request-ID")
               or request.form.get("CallSid")
               or request.form.get("MessageSid")
               or str(uuid.uuid4()))
        g.request_id = rid
        g._t0 = time.monotonic()
        log.info("INCOMING %s %s ip=%s ua=%s",
                 request.method, request.path,
                 request.headers.get("X-Forwarded-For", request.remote_addr),
                 request.headers.get("User-Agent"))

    @app.after_request
    def _after(resp):
        dt = int((time.monotonic() - getattr(g, "_t0", time.monotonic())) * 1000)
        resp.headers["X-Request-ID"] = getattr(g, "request_id", "-")
        # Skip health check logging to reduce noise
        if request.path != "/health":
            log.info("OUT %s %s status=%s dur_ms=%s len=%s",
                     request.method, request.path, resp.status_code, dt, resp.content_length)
        return resp

    @app.teardown_request
    def _teardown(exc):
        if exc is not None:
            log = logging.getLogger("errors")
            log.exception("Unhandled exception: %s", exc)

def install_sqlalchemy_slow_query_logging(app, db):
    """
    Logs queries slower than DB_SLOW_MS.
    Call from within app.app_context().
    """
    try:
        from sqlalchemy import event
        import time as _t
        logger = logging.getLogger("sqlalchemy.slow")

        @event.listens_for(db.engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault('query_start_time', []).append(_t.time())

        @event.listens_for(db.engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            t0 = conn.info['query_start_time'].pop(-1)
            total = (_t.time() - t0) * 1000
            if total >= SLOW_MS:
                logger.warning("SLOW_QUERY dur_ms=%d sql=%s params=%s", total, statement, parameters)
    except Exception as e:
        logging.getLogger(__name__).warning("Slow query logging not installed: %s", e)