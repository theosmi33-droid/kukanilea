from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask

import kukanilea_core_v3_fixed as core
from app.autonomy import ocr as ocr_mod
from app.autonomy.ocr import submit_ocr_for_source_file
from app.knowledge.core import knowledge_policy_update


def _mock_tesseract_binary(monkeypatch) -> None:
    def _resolve(requested_bin=None, env=None, *, platform_name=None):
        selected = str(requested_bin or "/usr/bin/tesseract")
        source = "explicit" if requested_bin else "path"
        return ocr_mod.ResolvedTesseractBin(
            requested=requested_bin,
            resolved_path=selected,
            exists=True,
            executable=True,
            allowlisted=True,
            allowlist_reason="matched_prefix",
            allowed_prefixes=("/usr/bin",),
            resolution_source=source,
        )

    monkeypatch.setattr(ocr_mod, "resolve_tesseract_binary", _resolve)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _insert_source_file(tenant_id: str, source_file_id: str, basename: str) -> None:
    con = sqlite3.connect(str(core.DB_PATH))
    try:
        con.execute(
            """
            INSERT INTO source_files(
              id, tenant_id, source_kind, basename, path_hash, fingerprint, status,
              last_seen_at, first_seen_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                source_file_id,
                tenant_id,
                "document",
                basename,
                "hash-2",
                "fp-2",
                "new",
                _now_iso(),
                _now_iso(),
            ),
        )
        con.commit()
    finally:
        con.close()


def test_ocr_subprocess_contract_and_redaction(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    knowledge_policy_update("TENANT_A", actor_user_id="dev", allow_ocr=True)
    source_file_id = "sf2"
    _insert_source_file("TENANT_A", source_file_id, "private.png")
    image_path = tmp_path / "private.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\npayload")

    captured: dict[str, object] = {}

    class _Proc:
        returncode = 0
        stdout = "Kontakt: user@example.com\nTelefon +49 170 1234567"
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _Proc()

    _mock_tesseract_binary(monkeypatch)
    monkeypatch.setattr(ocr_mod.subprocess, "run", _fake_run)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        AUTONOMY_OCR_TIMEOUT_SEC=12,
        AUTONOMY_OCR_MAX_CHARS=200_000,
        AUTONOMY_OCR_LANG="eng",
    )
    with app.app_context():
        result = submit_ocr_for_source_file(
            tenant_id="TENANT_A",
            actor_user_id="dev",
            source_file_id=source_file_id,
            abs_path=image_path,
        )

    assert result["ok"] is True
    assert isinstance(captured.get("cmd"), list)
    cmd = captured["cmd"]
    assert str(cmd[0]).endswith("/tesseract")
    assert cmd[2] == "stdout"
    assert cmd[3] == "-l"
    assert cmd[4] == "eng"
    kwargs = captured["kwargs"]
    assert kwargs["shell"] is False
    assert int(kwargs["timeout"]) == 12
    assert kwargs["stdin"] == ocr_mod.subprocess.DEVNULL

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT body
            FROM knowledge_chunks
            WHERE tenant_id='TENANT_A' AND source_type='ocr'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        assert row is not None
        body = str(row["body"] or "").lower()
        assert "user@example.com" not in body
        assert "+49 170" not in body
        assert "[redacted-email]" in body
    finally:
        con.close()


def test_ocr_subprocess_uses_tessdata_override(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    knowledge_policy_update("TENANT_A", actor_user_id="dev", allow_ocr=True)
    source_file_id = "sf3"
    _insert_source_file("TENANT_A", source_file_id, "override.png")
    image_path = tmp_path / "override.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\npayload")
    override_bin = tmp_path / "tesseract"
    override_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    override_bin.chmod(0o755)
    monkeypatch.setenv("KUKANILEA_TESSERACT_ALLOWED_PREFIXES", str(tmp_path))

    captured: dict[str, object] = {}

    class _Proc:
        returncode = 0
        stdout = "OCR TEXT"
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        captured["kwargs"] = kwargs
        return _Proc()

    _mock_tesseract_binary(monkeypatch)
    monkeypatch.setattr(ocr_mod.shutil, "which", lambda _name: None)
    monkeypatch.setattr(ocr_mod.subprocess, "run", _fake_run)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        AUTONOMY_OCR_TIMEOUT_SEC=8,
        AUTONOMY_OCR_MAX_CHARS=200_000,
        AUTONOMY_OCR_LANG="eng",
    )
    with app.app_context():
        result = submit_ocr_for_source_file(
            tenant_id="TENANT_A",
            actor_user_id="dev",
            source_file_id=source_file_id,
            abs_path=image_path,
            lang_override="deu",
            tessdata_dir="/opt/homebrew/share",
            tesseract_bin_override=str(override_bin),
        )

    assert result["ok"] is True
    cmd = captured["cmd"]
    assert cmd[0] == str(override_bin)
    assert "--tessdata-dir" in cmd
    assert cmd[cmd.index("--tessdata-dir") + 1] == "/opt/homebrew/share"
    assert "-l" in cmd
    assert cmd[cmd.index("-l") + 1] == "deu"
    kwargs = captured["kwargs"]
    assert kwargs["env"]["TESSDATA_PREFIX"] == "/opt/homebrew/share"


def test_ocr_subprocess_uses_env_overrides_when_no_explicit_args(
    tmp_path: Path, monkeypatch
) -> None:
    _init_core(tmp_path)
    knowledge_policy_update("TENANT_A", actor_user_id="dev", allow_ocr=True)
    source_file_id = "sf3-env"
    _insert_source_file("TENANT_A", source_file_id, "env-override.png")
    image_path = tmp_path / "env-override.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\npayload")
    override_bin = tmp_path / "tesseract"
    override_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    override_bin.chmod(0o755)
    monkeypatch.setenv("KUKANILEA_TESSERACT_ALLOWED_PREFIXES", str(tmp_path))
    monkeypatch.setenv("AUTONOMY_OCR_TESSERACT_BIN", str(override_bin))
    monkeypatch.setenv("AUTONOMY_OCR_TESSDATA_DIR", "/opt/homebrew/share")
    monkeypatch.setenv("AUTONOMY_OCR_LANG", "deu")

    captured: dict[str, object] = {}

    class _Proc:
        returncode = 0
        stdout = "OCR TEXT"
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        captured["kwargs"] = kwargs
        return _Proc()

    monkeypatch.setattr(ocr_mod.shutil, "which", lambda _name: None)
    monkeypatch.setattr(ocr_mod.subprocess, "run", _fake_run)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        AUTONOMY_OCR_TIMEOUT_SEC=8,
        AUTONOMY_OCR_MAX_CHARS=200_000,
        AUTONOMY_OCR_LANG="",
    )
    with app.app_context():
        result = submit_ocr_for_source_file(
            tenant_id="TENANT_A",
            actor_user_id="dev",
            source_file_id=source_file_id,
            abs_path=image_path,
        )

    assert result["ok"] is True
    cmd = captured["cmd"]
    assert cmd[0] == str(override_bin)
    assert "--tessdata-dir" in cmd
    assert cmd[cmd.index("--tessdata-dir") + 1] == "/opt/homebrew/share"
    assert "-l" in cmd
    assert cmd[cmd.index("-l") + 1] == "deu"
    assert result["tesseract_resolution_source"] == "env"
    kwargs = captured["kwargs"]
    assert kwargs["env"]["TESSDATA_PREFIX"] == "/opt/homebrew/share"


def test_run_tesseract_retry_guard(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "retry.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\npayload")

    class _ProcFail:
        returncode = 1
        stdout = ""
        stderr = "Failed loading language 'eng'"

    class _ProcOk:
        returncode = 0
        stdout = "TEXT"
        stderr = ""

    calls: list[list[str]] = []
    seq = [_ProcFail(), _ProcOk()]

    def _fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return seq.pop(0)

    _mock_tesseract_binary(monkeypatch)
    monkeypatch.setattr(ocr_mod.subprocess, "run", _fake_run)
    import app.devtools.tesseract_probe as probe_mod

    monkeypatch.setattr(
        probe_mod,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": True,
            "reason": "ok",
            "langs": ["deu", "eng"],
            "lang_selected": "deu",
            "tessdata_prefix": "/usr/share",
        },
    )

    text, error, _truncated, _stderr = ocr_mod._run_tesseract(
        image_path,
        lang="eng",
        timeout_sec=2,
        max_chars=1024,
        tessdata_dir=None,
        allow_retry=True,
    )
    assert error is None
    assert text == "TEXT"
    assert len(calls) == 2

    calls.clear()
    seq[:] = [_ProcFail()]
    text2, error2, _truncated2, _stderr2 = ocr_mod._run_tesseract(
        image_path,
        lang="eng",
        timeout_sec=2,
        max_chars=1024,
        tessdata_dir=None,
        allow_retry=False,
    )
    assert text2 is None
    assert error2 == "language_missing"
    assert len(calls) == 1


def test_run_tesseract_no_retry_on_timeout(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "timeout.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\npayload")

    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        raise ocr_mod.subprocess.TimeoutExpired(cmd, 1)

    _mock_tesseract_binary(monkeypatch)
    monkeypatch.setattr(ocr_mod.subprocess, "run", _fake_run)
    import app.devtools.tesseract_probe as probe_mod

    monkeypatch.setattr(
        probe_mod,
        "probe_tesseract",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not retry")),
    )

    text, error, _truncated, _stderr = ocr_mod._run_tesseract(
        image_path,
        lang="eng",
        timeout_sec=1,
        max_chars=1024,
        tessdata_dir=None,
        allow_retry=True,
    )
    assert text is None
    assert error == "timeout"
    assert len(calls) == 1


def test_run_tesseract_config_file_missing_classification(
    tmp_path: Path, monkeypatch
) -> None:
    image_path = tmp_path / "cfg.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\npayload")

    class _ProcFail:
        returncode = 1
        stdout = ""
        stderr = "read_params_file: Can't open config file"

    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return _ProcFail()

    _mock_tesseract_binary(monkeypatch)
    monkeypatch.setattr(ocr_mod.subprocess, "run", _fake_run)

    text, error, _truncated, _stderr = ocr_mod._run_tesseract(
        image_path,
        lang="eng",
        timeout_sec=1,
        max_chars=1024,
        tessdata_dir=None,
        allow_retry=True,
    )
    assert text is None
    assert error == "config_file_missing"
    assert len(calls) == 1


def test_classify_tesseract_path_allowlists_homebrew_on_darwin(monkeypatch) -> None:
    candidate = Path("/opt/homebrew/bin/tesseract")
    real = Path("/opt/homebrew/Cellar/tesseract/5.5.1/bin/tesseract")

    monkeypatch.setattr(
        Path,
        "exists",
        lambda self: str(self) in {str(candidate), str(real)},
        raising=False,
    )
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: str(self) in {str(candidate), str(real)},
        raising=False,
    )
    monkeypatch.setattr(
        ocr_mod.os,
        "access",
        lambda path, _mode: str(path) in {str(candidate), str(real)},
    )
    monkeypatch.setattr(
        ocr_mod.os.path,
        "realpath",
        lambda value: str(real) if str(value) == str(candidate) else str(value),
    )

    classified = ocr_mod.classify_tesseract_path(
        str(candidate),
        platform_name="darwin",
        env={},
    )
    assert classified["reason"] == "ok"
    assert classified["allowlisted"] is True


def test_classify_tesseract_path_accepts_realpath_prefix_match(
    monkeypatch,
) -> None:
    candidate = Path("/tmp/custom-link/tesseract")
    real = Path("/opt/homebrew/Cellar/tesseract/5.5.1/bin/tesseract")

    monkeypatch.setattr(
        Path,
        "exists",
        lambda self: str(self) in {str(candidate), str(real)},
        raising=False,
    )
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: str(self) in {str(candidate), str(real)},
        raising=False,
    )
    monkeypatch.setattr(
        ocr_mod.os,
        "access",
        lambda path, _mode: str(path) in {str(candidate), str(real)},
    )
    monkeypatch.setattr(
        ocr_mod.os.path,
        "realpath",
        lambda value: str(real) if str(value) == str(candidate) else str(value),
    )

    classified = ocr_mod.classify_tesseract_path(
        str(candidate),
        platform_name="darwin",
        env={},
    )
    assert classified["reason"] == "ok"
    assert classified["allowlisted"] is True


def test_classify_tesseract_path_reports_not_allowlisted(
    tmp_path: Path, monkeypatch
) -> None:
    custom_bin = tmp_path / "tesseract"
    custom_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    custom_bin.chmod(0o755)

    classified = ocr_mod.classify_tesseract_path(
        str(custom_bin),
        platform_name="darwin",
        env={},
    )
    assert classified["exists"] is True
    assert classified["executable"] is True
    assert classified["allowlisted"] is False
    assert classified["reason"] == "tesseract_not_allowlisted"


def test_run_tesseract_override_not_allowlisted(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\npayload")
    custom_bin = tmp_path / "tesseract"
    custom_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    custom_bin.chmod(0o755)

    monkeypatch.setattr(
        ocr_mod.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not invoke subprocess")
        ),
    )

    text, error, _truncated, _stderr = ocr_mod._run_tesseract(
        image_path,
        lang="eng",
        timeout_sec=2,
        max_chars=1024,
        tesseract_bin_override=str(custom_bin),
        allow_retry=False,
    )
    assert text is None
    assert error == "tesseract_not_allowlisted"


def test_run_tesseract_exec_failed_errno(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\npayload")
    override_bin = tmp_path / "tesseract"
    override_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    override_bin.chmod(0o755)
    monkeypatch.setenv("KUKANILEA_TESSERACT_ALLOWED_PREFIXES", str(tmp_path))

    def _fake_run(*_args, **_kwargs):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(ocr_mod.subprocess, "run", _fake_run)

    text, error, _truncated, stderr_tail = ocr_mod._run_tesseract(
        image_path,
        lang="eng",
        timeout_sec=2,
        max_chars=1024,
        tesseract_bin_override=str(override_bin),
        allow_retry=False,
    )
    assert text is None
    assert error == "tesseract_exec_failed"
    assert "errno=13" in str(stderr_tail or "")
