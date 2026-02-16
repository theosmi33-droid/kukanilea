from __future__ import annotations

from pathlib import Path

import app.devtools.tesseract_probe as probe_mod


class _Proc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_parse_list_langs_output_warning_tolerant() -> None:
    parsed = probe_mod.parse_list_langs_output(
        "List of available languages (2):\ndeu\nosd\n",
        "Error opening data file /Users/test/tessdata/eng.traineddata",
    )
    assert parsed["langs"] == ["deu", "osd"]
    assert parsed["has_warning"] is True
    assert parsed["warnings"]


def test_probe_bin_missing(monkeypatch) -> None:
    monkeypatch.setattr(probe_mod, "_resolve_bin", lambda _bin_path: None)
    result = probe_mod.probe_tesseract()
    assert result["ok"] is False
    assert result["reason"] == "tesseract_missing"
    assert result["tesseract_found"] is False


def test_probe_ok_with_warnings_when_langs_present(monkeypatch) -> None:
    monkeypatch.setattr(
        probe_mod, "_resolve_bin", lambda _bin_path: Path("/usr/bin/tesseract")
    )

    def _fake_run(cmd, **_kwargs):
        assert "--list-langs" in cmd
        return _Proc(
            1,
            stdout="List of available languages (2):\ndeu\nosd\n",
            stderr="Error opening data file /Users/test/eng.traineddata",
        )

    monkeypatch.setattr(probe_mod.subprocess, "run", _fake_run)
    result = probe_mod.probe_tesseract()
    assert result["ok"] is True
    assert result["reason"] == "ok_with_warnings"
    assert result["lang_selected"] == "deu"
    assert result["warnings"]


def test_probe_tessdata_missing_when_no_langs(monkeypatch) -> None:
    monkeypatch.setattr(
        probe_mod, "_resolve_bin", lambda _bin_path: Path("/usr/bin/tesseract")
    )
    monkeypatch.setattr(
        probe_mod.subprocess,
        "run",
        lambda cmd, **_kwargs: _Proc(
            1,
            stdout="",
            stderr="Error opening data file /broken/tessdata/eng.traineddata",
        ),
    )
    result = probe_mod.probe_tesseract()
    assert result["ok"] is False
    assert result["reason"] == "tessdata_missing"


def test_probe_language_missing_requested(monkeypatch) -> None:
    monkeypatch.setattr(
        probe_mod, "_resolve_bin", lambda _bin_path: Path("/usr/bin/tesseract")
    )
    monkeypatch.setattr(
        probe_mod.subprocess,
        "run",
        lambda cmd, **_kwargs: _Proc(
            0, stdout="List of available languages (1):\ndeu\n"
        ),
    )
    result = probe_mod.probe_tesseract(preferred_langs=["eng"])
    assert result["ok"] is False
    assert result["reason"] == "language_missing"
    assert result["langs"] == ["deu"]


def test_probe_sorts_langs_and_excludes_header(monkeypatch) -> None:
    monkeypatch.setattr(
        probe_mod, "_resolve_bin", lambda _bin_path: Path("/usr/bin/tesseract")
    )
    monkeypatch.setattr(
        probe_mod.subprocess,
        "run",
        lambda cmd, **_kwargs: _Proc(
            0, stdout="List of available languages (3):\nosd\ndeu\neng\n"
        ),
    )
    result = probe_mod.probe_tesseract()
    assert result["ok"] is True
    assert result["langs"] == ["deu", "eng", "osd"]
    assert result["lang_selected"] == "eng"


def test_probe_only_osd_is_language_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        probe_mod, "_resolve_bin", lambda _bin_path: Path("/usr/bin/tesseract")
    )
    monkeypatch.setattr(
        probe_mod.subprocess,
        "run",
        lambda cmd, **_kwargs: _Proc(
            0, stdout="List of available languages (1):\nosd\n"
        ),
    )
    result = probe_mod.probe_tesseract()
    assert result["ok"] is False
    assert result["reason"] == "language_missing"


def test_probe_sanitizes_stderr_tail_paths_and_markers(monkeypatch) -> None:
    monkeypatch.setattr(
        probe_mod, "_resolve_bin", lambda _bin_path: Path("/usr/bin/tesseract")
    )
    stderr = (
        "Error opening data file /Users/test/My Tesseract/tessdata/eng.traineddata\n"
        "pilot+test@example.com"
    )
    monkeypatch.setattr(
        probe_mod.subprocess,
        "run",
        lambda cmd, **_kwargs: _Proc(1, stdout="", stderr=stderr),
    )
    result = probe_mod.probe_tesseract()
    tail = str(result.get("stderr_tail") or "")
    assert "<path>" in tail
    assert "/Users/test" not in tail
    assert "pilot+test@example.com" not in tail
