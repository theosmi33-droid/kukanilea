from flask import Blueprint, jsonify
from app.core.boot_sequence import get_boot_status
from app.core.observer import get_system_status

bp = Blueprint('boot_api', __name__, url_prefix='/api/boot')

@bp.route('/status', methods=['GET'])
def boot_status():
    status = get_boot_status()
    return jsonify(status.get_progress())

@bp.route('/system-health', methods=['GET'])
def system_health():
    return jsonify(get_system_status())
