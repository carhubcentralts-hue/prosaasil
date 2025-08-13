from flask import jsonify

def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e): 
        return jsonify({"error":"not_found"}), 404

    @app.errorhandler(500)
    def internal(e):
        app.logger.exception("Unhandled server error")
        return jsonify({"error":"server_error"}), 500