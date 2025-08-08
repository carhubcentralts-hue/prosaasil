from flask import Blueprint

calendar_bp = Blueprint("calendar", __name__)

@calendar_bp.route("/", methods=["GET"])
def calendar_home():
    return {"message": "Calendar route placeholder"}, 200