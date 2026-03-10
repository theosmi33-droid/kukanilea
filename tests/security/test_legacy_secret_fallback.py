from __future__ import annotations

from pathlib import Path


LEGACY_UPLOAD = Path(__file__).resolve().parents[2] / "archive_legacy" / "kukanilea_upload.py"


def test_legacy_upload_uses_random_secret_fallback() -> None:
    text = LEGACY_UPLOAD.read_text(encoding="utf-8")

    assert "secrets.token_urlsafe(64)" in text
    assert "tophandwerk-dev-secret-change-me" not in text
