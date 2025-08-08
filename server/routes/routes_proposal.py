from flask import Blueprint

proposal_bp = Blueprint("proposal", __name__)

@proposal_bp.route("/", methods=["GET"])
def proposal_home():
    return {"message": "Proposal route placeholder"}, 200