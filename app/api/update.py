from flask import Blueprint, jsonify, request
from app.update import check_and_update, get_update_status
from app.database import get_db_connection

bp = Blueprint('update', __name__, url_prefix='/api/update')

@bp.route('/status', methods=['GET'])
def status():
    return jsonify(get_update_status())

@bp.route('/download', methods=['POST'])
def download():
    """Triggert den Download und die Vorbereitung des Updates."""
    # Wir führen es asynchron aus, um den Request nicht zu blockieren
    from flask import current_app
    
    def _async_download():
        check_and_update(show_notification=True)
        
    if hasattr(current_app, "executor"):
        current_app.executor.submit(_async_download)
        return jsonify({"status": "started", "message": "Download gestartet..."})
    else:
        # Fallback sync
        success = check_and_update(show_notification=True)
        if success:
            return jsonify({"status": "downloaded"})
        else:
            return jsonify({"error": "Update fehlgeschlagen"}), 500
