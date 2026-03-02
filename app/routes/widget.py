from flask import Blueprint, request, jsonify, render_template
import logging
from app.core.llm_guardian import LLMGuardian
from app.core.widget_db import WidgetDatabase
from app.core.license_guardian import get_guardian
from pathlib import Path

# Wir initialisieren die Route
bp = Blueprint("widget", __name__, url_prefix="/widget")
logger = logging.getLogger("kukanilea.widget")

# Singletons für das Widget
guardian = LLMGuardian()
# Die DB liegt isoliert im Nutzerverzeichnis
widget_db = WidgetDatabase(Path("instance/widget/floating_brain.sqlite"))

@bp.route("/")
def render_widget():
    """Rendert die kompakte Floating-Widget UI."""
    return render_template("widget.html")

@bp.route("/api/ask", methods=["POST"])
def ask_local_llm():
    """
    API Endpunkt für das Widget.
    1. Checkt die Lizenz (Deny-by-default)
    2. Checkt den Prompt auf Injections (Taint-Analysis)
    3. Führt Inferenz durch (LLMFit lokales Modell)
    4. Speichert den Verlauf in der WidgetDB (60 Tage Retention)
    """
    # 1. Lizenz Check
    license_status = get_guardian().verify_local_license()
    if not license_status["valid"]:
        return jsonify({"error": "Lizenz ungültig oder abgelaufen.", "details": license_status["reason"]}), 403

    data = request.json
    user_prompt = data.get("prompt", "")

    # 2. Guardian Check & Payload Konstruktion
    try:
        # Lade letzten Kontext für das Gedächtnis
        history = widget_db.get_recent_history(limit=5)
        safe_payload = guardian.construct_safe_payload(user_prompt, history=history)
    except ValueError as ve:
        # Prompt Injection erkannt!
        widget_db.record_interaction(user_prompt, "BLOCKIERT", "N/A", flagged=True)
        return jsonify({"error": str(ve)}), 400

    # 3. Lokale LLM Inferenz (Mock für LLMFit / Ollama Integration)
    # Hier würde in der Realität der Aufruf an localhost:11434 (Ollama) oder Llama-CPP gehen
    llm_response = "[Lokal generiert] Ich habe die Anfrage verstanden und bearbeite das Dokument lokal."
    model_used = "kukanilea-handwerk-v1 (LLMFit)"

    # 4. Speichern und Cleanup
    widget_db.record_interaction(user_prompt, llm_response, model_used)
    widget_db.enforce_retention_policy(days=60) # Stellt sicher, dass alte Daten gelöscht werden

    return jsonify({"response": llm_response, "model": model_used})
