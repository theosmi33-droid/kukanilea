from __future__ import annotations

from pathlib import Path


def test_is_allowed_path_blocks_sibling_prefix_and_allows_root(monkeypatch, tmp_path: Path):
    import app.web as web

    eingang = tmp_path / "eingang"
    base_path = tmp_path / "base"
    pending_dir = tmp_path / "pending"
    done_dir = tmp_path / "done"
    for d in (eingang, base_path, pending_dir, done_dir):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(web, "EINGANG", eingang)
    monkeypatch.setattr(web, "BASE_PATH", base_path)
    monkeypatch.setattr(web, "PENDING_DIR", pending_dir)
    monkeypatch.setattr(web, "DONE_DIR", done_dir)

    allowed_file = base_path / "tenant" / "ok.pdf"
    allowed_file.parent.mkdir(parents=True, exist_ok=True)
    allowed_file.write_text("ok", encoding="utf-8")

    sibling_prefix = tmp_path / "base_evil" / "steal.pdf"
    sibling_prefix.parent.mkdir(parents=True, exist_ok=True)
    sibling_prefix.write_text("bad", encoding="utf-8")

    assert web._is_allowed_path(allowed_file) is True
    assert web._is_allowed_path(sibling_prefix) is False
