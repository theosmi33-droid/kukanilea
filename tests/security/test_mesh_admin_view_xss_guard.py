from __future__ import annotations


def test_admin_mesh_escapes_peer_metadata(admin_client, monkeypatch):
    _app, client = admin_client
    from app.core.mesh_network import MeshNetworkManager

    payload = '<img src=x onerror=alert("xss")>'
    ip_payload = "<svg/onload=alert(1)>"

    def _fake_get_peers(self):
        return [
            {
                "node_id": "HUB-ATTACK",
                "name": payload,
                "type": "ZimaBlade",
                "status": "ONLINE",
                "last_ip": ip_payload,
            }
        ]

    monkeypatch.setattr(MeshNetworkManager, "get_peers", _fake_get_peers)

    response = client.get("/admin/mesh")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert payload not in body
    assert ip_payload not in body
    assert "&lt;img src=x onerror=alert(&#34;xss&#34;)&gt;" in body
    assert "&lt;svg/onload=alert(1)&gt;" in body
