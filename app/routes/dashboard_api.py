from flask import Blueprint, jsonify
from ..auth import login_required
from app.security import csrf_protected
from app.core.integrity_check import run_vault_selftest

dashboard_bp = Blueprint("dashboard_api", __name__)

@dashboard_bp.route("/selftest", methods=["POST"])
@login_required
@csrf_protected
def vault_selftest():
    """
    Triggers a manual self-test of the document vault.
    Returns the integrity status.
    """
    try:
        results = run_vault_selftest()
        return jsonify({
            "status": "OK" if results.get("integrity_ok") else "ERROR",
            "details": results,
            "message": "Vault Integritätstest abgeschlossen."
        })
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500
