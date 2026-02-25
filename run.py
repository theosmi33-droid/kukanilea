#!/usr/bin/env python3
"""
run.py
Zentraler Einstiegspunkt für KUKANILEA Gold v1.5.0.
Steuert Desktop-, Server- und API-Modus via argparse.
"""
import argparse
import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor

# Verzeichnis-Wiring
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app import create_app

# Concurrency-Tuning für Gold v1.5.0
MAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

def optimize_db():
    """Optimiert FTS5 Such-Indizes für Zero-Latenz."""
    import sqlite3
    from app.config import Config
    try:
        db_path = str(Config.CORE_DB)
        if not os.path.exists(db_path):
            return

        con = sqlite3.connect(db_path)
        # Suche nach FTS5 Tabellen
        fts_tables = ["knowledge_fts", "docs_fts", "knowledge_search", "article_search"]
        for table in fts_tables:
            try:
                con.execute(f"INSERT INTO {table}({table}) VALUES('optimize');")
                print(f"[DB] FTS5 Optimierung für {table} abgeschlossen.")
            except: pass
        con.close()
    except Exception as e:
        print(f"[DB] Optimierung übersprungen: {e}")

def main():
    parser = argparse.ArgumentParser(description="KUKANILEA Gold v1.5.0 Runner")
    parser.add_argument("--desktop", action="store_true", help="Startet im Desktop-Modus (Native WebView)")
    parser.add_argument("--server", action="store_true", help="Startet im klassischen Server-Modus (Waitress)")
    parser.add_argument("--hub", action="store_true", help="Startet im Workshop-Hub Modus (Optimiert für ZimaBlade)")
    parser.add_argument("--api-only", action="store_true", help="Deaktiviert Web-UI, startet nur API-Endpoints")
    parser.add_argument("--show-hwid", action="store_true", help="Zeigt die Hardware-ID (HWID) des Rechners an")
    parser.add_argument("--port", type=int, default=5051, help="Port (Standard: 5051)")
    parser.add_argument("--host", default="127.0.0.1", help="Host (Standard: 127.0.0.1)")
    parser.add_argument("--debug", action="store_true", help="Aktiviert Flask Debug-Modus")
    
    args = parser.parse_args()

    if args.show_hwid:
        from app.core.license_manager import license_manager
        print(f"Hardware-ID (HWID): {license_manager.hardware_id}")
        return

    # Pre-Flight
    optimize_db()

    # System-Settings für create_app
    settings = {
        "worker_threads": MAX_WORKERS,
        "api_only": args.api_only,
        "hub_mode": args.hub
    }
    
    if args.hub:
        print("[HUB] Workshop-Hub Modus aktiviert. Optimiere für ZimaBlade...")
        os.environ["KUKANILEA_MODE"] = "hub"
        # Hub übernimmt schwere Aufgaben (Inferenz-Dienst)
        os.environ["OLLAMA_MAX_LOADED_MODELS"] = "3"
        # Host auf 0.0.0.0 für Mesh-Erreichbarkeit erzwingen falls nicht anders gesetzt
        if args.host == "127.0.0.1":
            args.host = "0.0.0.0"

    app = create_app(system_settings=settings)
    app.executor = executor # Globaler Executor für Background-Tasks

    # Gold: Background Update Check
    def _check_updates_task():
        import time
        from datetime import datetime
        from app.update import check_and_update, get_update_status
        from app.database import get_db_connection
        
        while True:
            try:
                # Prüfe, ob seit 24h kein Check
                with get_db_connection() as conn:
                    row = conn.execute("SELECT last_checked FROM update_status WHERE id=1").fetchone()
                    should_check = True
                    if row and row[0]:
                        try:
                            # Handling ISO strings from SQLite
                            last_str = row[0]
                            if " " in last_str: # Simple SQLite CURRENT_TIMESTAMP format
                                last = datetime.strptime(last_str, "%Y-%m-%d %H:%M:%S")
                            else:
                                last = datetime.fromisoformat(last_str)
                            delta = datetime.now() - last
                            if delta.total_seconds() < 86400:
                                should_check = False
                        except: pass
                
                if should_check:
                    check_and_update(show_notification=False)
            except: pass
            time.sleep(3600) # Check every hour if we should do the 24h check

    executor.submit(_check_updates_task)

    @app.route("/health")
    def simple_health():
        return {"status": "ok", "version": "1.5.0-gold"}

    if args.desktop:
        print("[START] Starte KUKANILEA im Desktop-Modus...")
        from app.desktop import run_native_desktop
        # Wir lassen desktop.py sein eigenes Ding machen, 
        # da es uvicorn nutzt und wir hier eine Flask app haben.
        # In einer idealen Welt würde run_native_desktop die 'app' entgegennehmen.
        run_native_desktop(title="KUKANILEA Business OS", debug=args.debug)
    elif args.server or args.api_only or args.hub:
        mode_str = "HUB" if args.hub else ("API-ONLY" if args.api_only else "SERVER")
        print(f"[START] Starte KUKANILEA im {mode_str} Modus auf {args.host}:{args.port}")
        
        if args.debug:
            app.run(host=args.host, port=args.port, debug=True)
        else:
            from waitress import serve
            serve(app, host=args.host, port=args.port, threads=MAX_WORKERS)
    else:
        # Default: Server Modus
        print(f"[START] Standard-Modus: Server auf {args.host}:{args.port}")
        from waitress import serve
        serve(app, host=args.host, port=args.port, threads=MAX_WORKERS)

if __name__ == "__main__":
    main()
