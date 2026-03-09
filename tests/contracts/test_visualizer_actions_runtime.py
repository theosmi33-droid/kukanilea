from __future__ import annotations

import base64


def test_visualizer_summary_build_action_returns_summary(auth_client, tmp_path, monkeypatch):
    source_file = tmp_path / "tenant-x" / "viz.csv"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("name,value\nA,1\n", encoding="utf-8")
    src_b64 = base64.b64encode(str(source_file).encode("utf-8")).decode("ascii")

    monkeypatch.setattr("app.web.current_tenant", lambda: "tenant-x")
    monkeypatch.setattr("app.routes.visualizer.BASE_PATH", tmp_path)
    monkeypatch.setattr("app.routes.visualizer._is_allowed_path", lambda _path: True)

    monkeypatch.setattr(
        "app.routes.visualizer.build_visualizer_payload",
        lambda *_args, **_kwargs: {
            "kind": "sheet",
            "sheet": {"rows": 1, "cols": 2},
            "file": {"name": "viz.csv"},
        },
    )

    response = auth_client.post("/api/visualizer/actions/summary.build", json={"source": src_b64})
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert "summary" in body["result"]


def test_visualizer_summary_build_action_degrades_without_backend(auth_client, tmp_path, monkeypatch):
    source_file = tmp_path / "tenant-x" / "viz.csv"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("name,value\nA,1\n", encoding="utf-8")
    src_b64 = base64.b64encode(str(source_file).encode("utf-8")).decode("ascii")

    monkeypatch.setattr("app.web.current_tenant", lambda: "tenant-x")
    monkeypatch.setattr("app.routes.visualizer.BASE_PATH", tmp_path)
    monkeypatch.setattr("app.routes.visualizer._is_allowed_path", lambda _path: True)
    monkeypatch.setattr("app.routes.visualizer.build_visualizer_payload", None)

    response = auth_client.post("/api/visualizer/actions/summary.build", json={"source": src_b64})
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"] == "visualizer_logic_missing"


def test_visualizer_summary_build_action_rejects_forbidden_path(auth_client, tmp_path, monkeypatch):
    source_file = tmp_path / "viz.csv"
    source_file.write_text("name,value\nA,1\n", encoding="utf-8")
    src_b64 = base64.b64encode(str(source_file).encode("utf-8")).decode("ascii")

    monkeypatch.setattr("app.routes.visualizer._is_allowed_path", lambda _path: False)

    response = auth_client.post("/api/visualizer/actions/summary.build", json={"source": src_b64})
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"] == "forbidden_path"


def test_visualizer_summary_build_action_rejects_cross_tenant_path(auth_client, tmp_path, monkeypatch):
    source_file = tmp_path / "tenant-y" / "secret.csv"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("name,value\nA,1\n", encoding="utf-8")
    src_b64 = base64.b64encode(str(source_file).encode("utf-8")).decode("ascii")

    monkeypatch.setattr("app.web.current_tenant", lambda: "tenant-x")
    monkeypatch.setattr("app.routes.visualizer.BASE_PATH", tmp_path)
    monkeypatch.setattr("app.routes.visualizer._is_allowed_path", lambda _path: True)

    response = auth_client.post("/api/visualizer/actions/summary.build", json={"source": src_b64})
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"] == "forbidden_tenant_path"
