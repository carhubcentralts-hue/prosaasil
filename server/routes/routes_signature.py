from flask import Blueprint

signature_bp = Blueprint("signature", __name__)

@signature_bp.route("/", methods=["GET"])
def signature_home():
    return {"message": "Signature route placeholder"}, 200