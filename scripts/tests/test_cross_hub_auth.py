"""
scripts/tests/test_cross_hub_auth.py
Integrationstest für Distributed Identity & Offline-SSO.
Simuliert zwei Hubs und verifiziert die kryptographische Token-Validierung.
"""

import sys
import os
import json
import sqlite3
from pathlib import Path

# Pfad-Setup
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from app.core.auth.token_factory import token_factory
from app.core.auth.mesh_validator import verify_mesh_token
from app.config import Config

def run_integration_test():
    print("--- KUKANILEA MESH AUTH INTEGRATION TEST ---")
    
    # 1. Setup Mock DB für Registry
    db_path = "instance/test_mesh_identities.sqlite3"
    if os.path.exists(db_path): os.remove(db_path)
    
    Config.CORE_DB = Path(db_path)
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE mesh_identities(
            user_uuid TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            home_hub_id TEXT NOT NULL,
            public_key_hex TEXT NOT NULL,
            roles_json TEXT NOT NULL,
            signature_hex TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    # 2. Simuliere Hub A: Erstelle ein SIT Token für einen User
    user_uuid = "user-123-abc"
    username = "Meister_Gerd"
    roles = ["ADMIN"]
    
    print(f"[Hub A] Erstelle SIT für {username}...")
    token = token_factory.create_sit(user_uuid, username, roles)
    pub_key = token_factory.get_public_key_hex()
    
    # 3. Simuliere Sync: Hub B lernt den Public Key von Hub A für diesen User
    print(f"[Sync] Übertrage Identität von Hub A zu Hub B Registry...")
    con.execute("""
        INSERT INTO mesh_identities (user_uuid, username, home_hub_id, public_key_hex, roles_json, signature_hex, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_uuid, username, "HUB-A", pub_key, json.dumps(roles), "MOCK_SIG", "2026-02-24"))
    con.commit()
    con.close()
    
    # 4. Simuliere Hub B: Verifiziere das Token
    print(f"[Hub B] Empfange Token und verifiziere lokal...")
    payload = verify_mesh_token(token)
    
    if payload and payload["name"] == username:
        print(f"✅ SUCCESS: Cross-Hub Login für {username} verifiziert!")
        print(f"   Rollen: {payload['roles']}")
        print(f"   Node-ID: {payload['iss']}")
    else:
        print("❌ FAILURE: Token-Verifizierung fehlgeschlagen.")
        sys.exit(1)

    # Cleanup
    if os.path.exists(db_path): os.remove(db_path)

if __name__ == "__main__":
    run_integration_test()
