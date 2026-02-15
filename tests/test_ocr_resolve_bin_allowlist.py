from __future__ import annotations

from pathlib import Path

from app.autonomy import ocr as ocr_mod


def test_resolve_tesseract_bin_requires_allowlisted_directory(monkeypatch) -> None:
    monkeypatch.setattr(ocr_mod.shutil, "which", lambda _name: "/tmp/tesseract")
    assert ocr_mod.resolve_tesseract_bin() is None

    monkeypatch.setattr(
        ocr_mod.shutil, "which", lambda _name: "/usr/local/bin/tesseract"
    )
    resolved = ocr_mod.resolve_tesseract_bin()
    assert resolved == Path("/usr/local/bin/tesseract")
