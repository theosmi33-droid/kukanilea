from __future__ import annotations

from pathlib import Path

import app.devtools.tesseract_probe as probe_mod


class _Proc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_probe_bin_missing(monkeypatch) -> None:
    monkeypatch.setattr(probe_mod, "_resolve_bin", lambda _bin_path: None)
    result = probe_mod.probe_tesseract()
    assert result["ok"] is False
    assert result["reason"] == "tesseract_missing"
    assert result["next_actions"]


def test_probe_list_langs_ok_without_tessdata_dir(monkeypatch) -> None:
    monkeypatch.setattr(
        probe_mod, "_resolve_bin", lambda _bin_path: Path("/usr/bin/tesseract")
    )

    def _fake_run(cmd, **_kwargs):
        assert "--list-langs" in cmd
        return _Proc(0, stdout="List of available languages (2):\neng\ndeu\n")

    monkeypatch.setattr(probe_mod.subprocess, "run", _fake_run)
    result = probe_mod.probe_tesseract()
    assert result["ok"] is True
    assert result["lang_used"] == "eng"
    assert "eng" in result["langs"]


def test_probe_falls_back_to_candidate_tessdata_dir(monkeypatch) -> None:
    monkeypatch.setattr(
        probe_mod, "_resolve_bin", lambda _bin_path: Path("/usr/bin/tesseract")
    )
    monkeypatch.setattr(
        probe_mod,
        "_candidate_tessdata_dirs",
        lambda **_kwargs: [("heuristic", Path("/opt/homebrew/share/tessdata"))],
    )
    calls: list[list[str]] = []

    def _fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        if "--tessdata-dir" in cmd:
            return _Proc(0, stdout="List of available languages (1):\neng\n")
        return _Proc(1, stderr="Error opening data file /bad/eng.traineddata")

    monkeypatch.setattr(probe_mod.subprocess, "run", _fake_run)
    result = probe_mod.probe_tesseract()
    assert result["ok"] is True
    assert result["tessdata_source"] == "heuristic"
    assert any("--tessdata-dir" in call for call in calls)


def test_probe_fallback_language_when_eng_missing(monkeypatch) -> None:
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
    result = probe_mod.probe_tesseract()
    assert result["ok"] is True
    assert result["lang_used"] == "deu"
    assert result["next_actions"]


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


def test_probe_sanitizes_stderr_tail(monkeypatch) -> None:
    monkeypatch.setattr(
        probe_mod, "_resolve_bin", lambda _bin_path: Path("/usr/bin/tesseract")
    )
    err = "Error opening data file /Users/test/eng.traineddata pilot+test@example.com"
    monkeypatch.setattr(
        probe_mod.subprocess,
        "run",
        lambda cmd, **_kwargs: _Proc(1, stdout="", stderr=err),
    )
    result = probe_mod.probe_tesseract()
    assert result["ok"] is False
    assert result["reason"] in {"tessdata_missing", "tesseract_failed"}
    assert "<path>" in str(result.get("stderr_tail") or "")
    assert "pilot+test@example.com" not in str(result.get("stderr_tail") or "")
