```diff
diff --git a/app/api.py b/app/api.py
index ca71b17..0c523a6 100644
--- a/app/api.py
+++ b/app/api.py
@@ -1,7 +1,7 @@
 from __future__ import annotations
 
 import sqlite3
-from datetime import datetime, timezone
+
 from flask import Blueprint, current_app, jsonify
 
 from .rate_limit import search_limiter
@@ -53,43 +53,46 @@ def health():
 def mesh_handshake():
     """Handles incoming handshake requests from peer Hubs."""
     from flask import request
+
     from app.core.mesh_identity import (
         HANDSHAKE_ACK_PURPOSE,
         HANDSHAKE_INIT_PURPOSE,
         create_handshake_envelope,
         verify_handshake_envelope,
     )
     from app.core.mesh_network import MeshNetworkManager
-    from app.core.mesh_identity import verify_signature, sign_message, ensure_mesh_identity
-    import json
 
     body = request.json
-    data = body.get("data")
-    sig = body.get("signature")
-
-    if not data or not sig:
+    if not isinstance(body, dict):
         return jsonify(ok=False, error="invalid_request"), 400
 
-    # Verify peer signature
-    peer_pub_key = data.get("public_key")
-    if not verify_signature(peer_pub_key, json.dumps(data, sort_keys=True).encode(utf-8), sig):
-        return jsonify(ok=False, error="invalid_signature"), 401
+    ok, reason, peer = verify_handshake_envelope(
+        body,
+        expected_purpose=HANDSHAKE_INIT_PURPOSE,
+    )
+    if not ok or not peer:
+        return jsonify(ok=False, error=reason), 401
+
+    challenge = str(peer.get("challenge") or "")
+    if not challenge:
+        return jsonify(ok=False, error="invalid_request"), 400
 
     # Register peer locally
     auth_db = current_app.extensions["auth_db"]
     manager = MeshNetworkManager(auth_db)
     manager.register_peer(
-        data["node_id"],
-        data["name"],
-        data["public_key"],
+        str(peer["node_id"]),
+        str(peer["name"]),
+        str(peer["public_key"]),
         request.remote_addr
     )
 
-    # Respond with our identity
-    my_pub, my_node = ensure_mesh_identity()
-    response_data = {
-        "node_id": my_node,
-        "name": current_app.config.get("APP_NAME", "KUKANILEA Hub"),
-        "public_key": my_pub,
-        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
-    }
-    my_sig = sign_message(json.dumps(response_data, sort_keys=True).encode(utf-8))
-
-    return jsonify(ok=True, peer=response_data, signature=my_sig)
+    response_envelope = create_handshake_envelope(
+        name=current_app.config.get("APP_NAME", "KUKANILEA Hub"),
+        purpose=HANDSHAKE_ACK_PURPOSE,
+        challenge=challenge,
+    )
+    return jsonify(ok=True, **response_envelope, peer=response_envelope["data"])
 
 
 @bp.get("/outbound/status")
-```
