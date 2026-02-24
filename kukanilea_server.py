#!/usr/bin/env python3
"""
kukanilea_server.py
Gold-Edition Entrypoint mit First-Run Guard.
"""
import sys
import os
import logging
from pathlib import Path

# Add project root to sys.path if frozen
if getattr(sys, 'frozen', False):
    os.environ['KUKANILEA_FROZEN'] = "1"
    # Ensure logs and instance are in user-space, not in read-only app bundle
    # macOS: ~/Library/Application Support/KUKANILEA
    # Windows: %APPDATA%/KUKANILEA
    from app.config import get_data_dir
    os.environ['KUKANILEA_USER_DATA_ROOT'] = str(get_data_dir())

from app.hardware_detection import init_hardware_detection
from app.core.license_manager import license_manager
from app import create_app

# 1. Hardware analysieren
SYSTEM_SETTINGS = init_hardware_detection()

# 2. Lizenz-Check (Gatekeeper)
is_activated = license_manager.is_valid()

if not is_activated:
    print("⚠️  System nicht aktiviert. Starte Onboarding-Wizard...")
    # Wir erstellen die App, aber der _enforce_activation middleware in app/__init__.py
    # wird alle Requests auf /activate umleiten.
    app = create_app(system_settings=SYSTEM_SETTINGS)
else:
    print("✅ System aktiviert. Starte Vollbetrieb.")
    app = create_app(system_settings=SYSTEM_SETTINGS)

if __name__ == "__main__":
    from waitress import serve
    # In der Gold-Edition lauschen wir nur lokal für maximale Sicherheit
    serve(app, host="127.0.0.1", port=5051, threads=SYSTEM_SETTINGS.get('worker_threads', 4))
