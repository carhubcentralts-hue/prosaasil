def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e): 
        return {"error": "not_found"}, 404
    
    @app.errorhandler(500)
    def server_error(e): 
        return {"error": "server_error"}, 500