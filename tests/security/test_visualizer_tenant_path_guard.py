from __future__ import annotations

from pathlib import Path

from app.routes.visualizer import _is_tenant_visualizer_path


def test_tenant_visualizer_path_guard_accepts_same_tenant(tmp_path, monkeypatch):
    import app.routes.visualizer as visualizer

    monkeypatch.setattr(visualizer, "BASE_PATH", tmp_path)
    monkeypatch.setattr(visualizer, "EINGANG", tmp_path / "eingang")

    target = tmp_path / "tenant-a" / "sample.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("name,value\nA,1\n", encoding="utf-8")

    assert _is_tenant_visualizer_path(target, "tenant-a") is True


def test_tenant_visualizer_path_guard_rejects_other_tenant(tmp_path, monkeypatch):
    import app.routes.visualizer as visualizer

    monkeypatch.setattr(visualizer, "BASE_PATH", tmp_path)
    monkeypatch.setattr(visualizer, "EINGANG", tmp_path / "eingang")

    target = tmp_path / "tenant-b" / "sample.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("name,value\nA,1\n", encoding="utf-8")

    assert _is_tenant_visualizer_path(target, "tenant-a") is False
