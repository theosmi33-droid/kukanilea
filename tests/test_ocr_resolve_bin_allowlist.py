from __future__ import annotations

from pathlib import Path

from app.autonomy import ocr as ocr_mod


def test_resolve_tesseract_bin_requires_allowlisted_directory(monkeypatch) -> None:
    known = {
        "/tmp/tesseract",
        "/usr/local/bin/tesseract",
    }
    monkeypatch.setattr(
        Path,
        "exists",
        lambda self: str(self) in known,
        raising=False,
    )
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: str(self) in known,
        raising=False,
    )
    monkeypatch.setattr(ocr_mod.os, "access", lambda path, _mode: str(path) in known)

    monkeypatch.setattr(ocr_mod.shutil, "which", lambda _name: "/tmp/tesseract")
    assert ocr_mod.resolve_tesseract_bin() is None

    monkeypatch.setattr(
        ocr_mod.shutil, "which", lambda _name: "/usr/local/bin/tesseract"
    )
    resolved = ocr_mod.resolve_tesseract_bin()
    assert resolved == Path("/usr/local/bin/tesseract")


def test_resolve_tesseract_binary_prefers_explicit(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "tesseract"
    custom.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    custom.chmod(0o755)
    monkeypatch.setenv("KUKANILEA_TESSERACT_ALLOWED_PREFIXES", str(tmp_path))
    monkeypatch.setattr(
        ocr_mod.shutil,
        "which",
        lambda _name, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not use PATH")
        ),
    )

    resolved = ocr_mod.resolve_tesseract_binary(requested_bin=str(custom))
    assert resolved.resolution_source == "explicit"
    assert resolved.exists is True
    assert resolved.executable is True
    assert resolved.allowlisted is True
    assert resolved.resolved_path


def test_resolve_tesseract_binary_uses_env_override(
    monkeypatch, tmp_path: Path
) -> None:
    custom = tmp_path / "tesseract"
    custom.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    custom.chmod(0o755)
    monkeypatch.setenv("KUKANILEA_TESSERACT_ALLOWED_PREFIXES", str(tmp_path))
    monkeypatch.setenv("AUTONOMY_OCR_TESSERACT_BIN", str(custom))
    monkeypatch.setattr(
        ocr_mod.shutil,
        "which",
        lambda _name, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not use PATH when env override exists")
        ),
    )

    resolved = ocr_mod.resolve_tesseract_binary(requested_bin=None)
    assert resolved.resolution_source == "env"
    assert resolved.exists is True
    assert resolved.executable is True
    assert resolved.allowlisted is True
    assert resolved.resolved_path
