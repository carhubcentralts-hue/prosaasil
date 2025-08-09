from flask import jsonify

def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error":"not_found","detail":"resource not found"}), 404

    @app.errorhandler(500)
    def internal(e):
        app.logger.exception("Unhandled server error")
        return jsonify({"error":"server_error"}), 500

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error":"forbidden","detail":"access denied"}), 403

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error":"unauthorized","detail":"authentication required"}), 401