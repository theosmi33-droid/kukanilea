"""
app/api/license_provisioning.py
Automatisierter Lizenz-Provisioning Workflow.
Erlaubt die Aktivierung von Lizenzen via API (z.B. nach Shop-Kauf).
"""

from flask import Blueprint, jsonify, request, current_app
from app.core.license_manager import license_manager
from app.auth import login_required, require_role

bp = Blueprint("license_provisioning", __name__, url_prefix="/api/license")

@bp.post("/activate")
@login_required
@require_role("ADMIN")
def activate_license():
    """
    Aktiviert eine Lizenz durch Einreichung eines Schlüssels.
    """
    payload = request.get_json() or {}
    license_key = payload.get("key")
    
    if not license_key:
        return jsonify(ok=False, message="Lizenzschlüssel fehlt."), 400
        
    try:
        # Wir nutzen den bestehenden license_manager
        success = license_manager.verify_and_install(license_key)
        
        if success:
            return jsonify(
                ok=True, 
                message="KUKANILEA Gold wurde erfolgreich aktiviert.",
                hwid=license_manager.hardware_id
            )
        else:
            return jsonify(ok=False, message="Ungültiger Schlüssel."), 403
            
    except Exception as e:
        return jsonify(ok=False, message=f"Aktivierungsfehler: {str(e)}"), 500

@bp.get("/status")
@login_required
def license_status():
    """Gibt den aktuellen Lizenzstatus zurück."""
    is_valid = license_manager.is_valid()
    return jsonify(
        active=is_valid,
        hwid=license_manager.hardware_id,
        plan="GOLD" if is_valid else "TRIAL"
    )
