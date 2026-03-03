from flask import Blueprint, jsonify
from app.auth import login_required
from app.core.integrity_check import run_vault_selftest

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/selftest", methods=["POST"])
@login_required
def vault_selftest():
    """
    Triggers a manual self-test of the document vault.
    Returns the integrity status.
    """
    try:
        # Assuming run_vault_selftest exists or creating a mock if not
        results = run_vault_selftest()
        return jsonify({
            "status": "OK" if results.get("integrity_ok") else "ERROR",
            "details": results,
            "message": "Vault Integritätstest abgeschlossen."
        })
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500
