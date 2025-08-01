from app import app
import routes  # Main routes
import crm_routes_additional  # Additional CRM routes
import whatsapp_routes  # WhatsApp integration routes

# CRM Blueprint already registered in routes.py

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
