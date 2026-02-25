"""
app/api/p2p.py
API-Endpunkte für den lokalen Mesh-Sync.
"""

from flask import Blueprint, jsonify, request, current_app, render_template_string
from app.auth import login_required, require_role

bp = Blueprint("p2p", __name__, url_prefix="/api/p2p")

PEER_LIST_TEMPLATE = """
{% if peers %}
  <div class="space-y-2">
    {% for peer in peers %}
      <div class="flex items-center justify-between p-3 bg-zinc-50 rounded-xl border border-zinc-100">
        <div class="flex items-center gap-3">
          <div class="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
          <div>
            <div class="text-sm font-bold">{{ peer.address }}</div>
            <div class="text-[10px] text-zinc-400 uppercase tracking-widest">{{ peer.port }} · v1.5.0</div>
          </div>
        </div>
        <button class="px-3 py-1 text-[10px] font-bold uppercase btn-outline rounded-lg" disabled>Synchronisiert</button>
      </div>
    {% endfor %}
  </div>
{% else %}
  <div class="flex items-center gap-2 text-xs text-zinc-400 italic">
    <div class="w-2 h-2 rounded-full bg-zinc-200"></div>
    Keine anderen Instanzen im Netzwerk gefunden.
  </div>
{% endif %}
"""

@bp.get("/peers")
@login_required
def list_peers():
    """Gibt alle im WLAN gefundenen KUKANILEA-Instanzen zurück."""
    mesh = getattr(current_app, "mesh", None)
    peers = mesh.get_active_peers() if mesh else []
    
    if "HX-Request" in request.headers:
        return render_template_string(PEER_LIST_TEMPLATE, peers=peers)
    
    return jsonify(peers=peers)

@bp.post("/sync/request")
@login_required
def sync_request():
    """Wird von einem anderen Peer aufgerufen, um einen Sync zu starten."""
    payload = request.get_json() or {}
    peer_id = payload.get("id")
    remote_delta = payload.get("delta")
    
    logger = current_app.logger
    logger.info(f"Mesh: Sync-Anfrage von Peer {peer_id} empfangen.")
    
    # 1. Fremde Änderungen anwenden (via CRDT Logic)
    if remote_delta:
        from app.core.mesh_logic import apply_remote_delta
        apply_remote_delta(remote_delta)
    
    # 2. Eigene Änderungen seit dem empfangenen Zeitstempel zurückgeben
    # (Bidirektionaler Abgleich in einem Request)
    from app.core.mesh_logic import get_latest_changes
    from app.core.crdt_engine import crdt
    
    local_delta = get_latest_changes(since_ts=str(payload.get("timestamp", 0)))
    
    return jsonify({
        "status": "ACCEPTED", 
        "message": "Delta-Abgleich abgeschlossen",
        "delta": local_delta
    })

@bp.post("/heartbeat")
def heartbeat():
    """Empfängt asynchrone Heartbeats der Mesh-Peers."""
    payload = request.get_json() or {}
    from app.core.fleet_monitor import record_heartbeat
    record_heartbeat(payload)
    return jsonify(status="ACK")

@bp.get("/fleet/status")
@login_required
def fleet_status():
    """Gibt den HTMX-Partial für den Global Health Monitor zurück."""
    from app.core.fleet_monitor import get_fleet_status, get_backup_status
    from app.core.hub_metrics import get_hub_vitals
    from flask import render_template
    
    fleet = get_fleet_status()
    hub_vitals = get_hub_vitals()
    backup_status = get_backup_status()
    
    return render_template("admin/_fleet_partial.html", 
                           fleet=fleet, 
                           hub_vitals=hub_vitals, 
                           backup_status=backup_status)
