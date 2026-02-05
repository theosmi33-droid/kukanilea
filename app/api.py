from __future__ import annotations

from flask import Blueprint, jsonify

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/ping")
def ping():
    return jsonify(ok=True)
