from flask import Blueprint

reports_bp = Blueprint("reports", __name__)

@reports_bp.route("/", methods=["GET"])
def reports_home():
    return {"message": "Reports route placeholder"}, 200