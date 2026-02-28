from flask import Blueprint, render_template, Response
import time
from pathlib import Path
from app.config import Config
from app.auth import login_required, require_role

bp = Blueprint("system_logs", __name__, url_prefix="/system")

@bp.route("/logs")
@login_required
@require_role(["DEV", "ADMIN"])
def view_logs():
    return render_template("system_logs.html", active_tab="settings")

@bp.route("/logs/stream")
@login_required
@require_role(["DEV", "ADMIN"])
def stream_logs():
    """SSE endpoint for live log streaming."""
    def generate():
        log_file = Config.LOG_DIR / "server_stderr.log"
        if not log_file.exists():
            yield "data: Log file not found.\n\n"
            return
            
        with open(log_file, "r") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                yield f"data: {line}\n\n"

    return Response(generate(), mimetype="text/event-stream")
