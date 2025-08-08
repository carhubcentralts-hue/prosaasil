from flask import Blueprint

crm_bp = Blueprint("crm", __name__)

@crm_bp.route("/customers", methods=["GET"])
def customers():
    # Will be implemented in step 6
    return {"message": "CRM route placeholder"}, 200