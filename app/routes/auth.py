# routes/auth.py — Authentication Routes
# Routes: /login  /register  /logout

from flask import Blueprint

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    return "Trekking Management App — Auth routes coming in Milestone 2"