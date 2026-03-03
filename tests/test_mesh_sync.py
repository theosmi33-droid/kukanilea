from __future__ import annotations

import os
import sys
import tempfile
import sqlite3
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure we can import app
sys.path.append(os.getcwd())

from app.core.mesh_network import MeshNetworkManager
from app.core.mesh_identity import ensure_mesh_identity, sign_message, verify_signature

def test_multi_hub_sync():
    print("Testing KUKANILEA Multi-Hub Sync POC...")
    
    with tempfile.NamedTemporaryFile() as tmp:
        db_path = tmp.name
        con = sqlite3.connect(db_path)
        con.execute("""
            CREATE TABLE mesh_nodes(
              node_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              public_key TEXT NOT NULL,
              last_ip TEXT,
              last_seen TEXT,
              status TEXT DEFAULT 'OFFLINE',
              trust_level INTEGER DEFAULT 0
            );
        """)
        con.commit()
        con.close()
        
        # Mock AuthDB
        mock_auth_db = MagicMock()
        def get_db():
            con = sqlite3.connect(db_path)
            con.row_factory = sqlite3.Row
            return con
        mock_auth_db._db.side_effect = get_db
        
        manager = MeshNetworkManager(mock_auth_db)
        
        # 1. Test Identity
        pub, node_id = ensure_mesh_identity()
        print(f"Local Node ID: {node_id}")
        assert node_id.startswith("HUB-")
        
        # 2. Test Signing
        msg = b"hello mesh"
        sig = sign_message(msg)
        assert verify_signature(pub, msg, sig) is True
        print("Identity and Signing: OK")
        
        # 3. Test Handshake (Mocked)
        peer_data = {
            "node_id": "HUB-PEER-99",
            "name": "External Hub",
            "public_key": pub, # Use same key for simplicity in mock
            "timestamp": "2026-02-28T16:00:00Z"
        }
        peer_sig = sign_message(json.dumps(peer_data, sort_keys=True).encode('utf-8'))
        
        with patch("app.core.mesh_network.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "peer": peer_data,
                "signature": peer_sig
            }
            mock_post.return_value = mock_resp
            
            success = manager.initiate_handshake("1.2.3.4")
            assert success is True
            
            peers = manager.get_peers()
            assert len(peers) == 1
            assert peers[0]["node_id"] == "HUB-PEER-99"
            print("Handshake and Peer Registration: OK")

    print("Multi-Hub Sync Test: PASS")

if __name__ == "__main__":
    test_multi_hub_sync()
