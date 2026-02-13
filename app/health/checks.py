from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from app.health.model import CheckResult

ALL_CHECKS = [
    "check_ai_gate_smoke",
    "check_bench_baseline",
    "check_config_load",
    "check_crm_tables",
    "check_db_access",
    "check_email_import_limits",
    "check_eventlog_chain",
    "check_python_env",
    "check_skills_registry",
    "check_web_routes_smoke",
]

_HEAVY_PREFIXES = (
    "chromadb",
    "sentence_transformers",
    "torch",
    "transformers",
    "tokenizers",
    "onnxruntime",
    "hnswlib",
    "numpy",
    "ollama",
)


def _mask_path(value: str) -> str:
    s = str(value)
    s = s.replace(str(Path.home()), "<home>")
    for marker in ["/tmp/", "/var/folders/", "\\Temp\\", "\\tmp\\"]:
        if marker in s:
            idx = s.find(marker)
            return s[:idx] + "<tmp>"
    return s


def check_python_env(runner) -> CheckResult:
    del runner
    details = {
        "version": sys.version,
        "platform": sys.platform,
        "executable": _mask_path(sys.executable),
    }
    return CheckResult(name="check_python_env", ok=True, severity="ok", details=details)


def check_config_load(runner) -> CheckResult:
    del runner
    try:
        import app.config as config

        paths = {}
        for attr in ["CORE_DB", "USER_DATA_ROOT", "AUTH_DB"]:
            if hasattr(config.Config, attr):
                paths[attr] = _mask_path(getattr(config.Config, attr))
        return CheckResult(
            name="check_config_load", ok=True, severity="ok", details={"paths": paths}
        )
    except Exception as exc:
        return CheckResult(
            name="check_config_load",
            ok=False,
            severity="fail",
            reason=f"Could not load config: {exc}",
            remediation="Set required environment and validate app/config.py imports.",
        )


def check_db_access(runner) -> CheckResult:
    if runner.mode == "ci":
        import kukanilea_core_v3_fixed as core

        with tempfile.TemporaryDirectory(prefix="kuka_health_ci_db_") as tmp:
            tmp_path = Path(tmp)
            old_db = core.DB_PATH
            old_base = core.BASE_PATH
            old_eingang = core.EINGANG
            old_pending = core.PENDING_DIR
            old_done = core.DONE_DIR
            try:
                core.DB_PATH = tmp_path / "core.db"
                core.BASE_PATH = tmp_path / "base"
                core.EINGANG = tmp_path / "eingang"
                core.PENDING_DIR = tmp_path / "pending"
                core.DONE_DIR = tmp_path / "done"
                core.db_init()
                con = sqlite3.connect(str(core.DB_PATH))
                try:
                    con.execute("SELECT 1").fetchone()
                finally:
                    con.close()
            finally:
                core.DB_PATH = old_db
                core.BASE_PATH = old_base
                core.EINGANG = old_eingang
                core.PENDING_DIR = old_pending
                core.DONE_DIR = old_done
        return CheckResult(name="check_db_access", ok=True, severity="ok")

    try:
        from app.config import Config

        db_path = Path(Config.CORE_DB)
        if not db_path.exists():
            return CheckResult(
                name="check_db_access",
                ok=False,
                severity="warn",
                reason=f"CORE_DB not found at {_mask_path(db_path)}",
                remediation="Fresh install: run app once to initialize DB.",
            )
        uri = f"file:{db_path}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        try:
            con.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        finally:
            con.close()
        return CheckResult(name="check_db_access", ok=True, severity="ok")
    except Exception as exc:
        return CheckResult(
            name="check_db_access",
            ok=False,
            severity="fail",
            reason=f"Could not open DB: {exc}",
            remediation="Check permissions and DB integrity.",
        )


def check_eventlog_chain(runner) -> CheckResult:
    from app.eventlog.core import event_append, event_hash

    if runner.mode == "ci":
        with tempfile.TemporaryDirectory(prefix="kuka_health_events_") as tmp:
            db = Path(tmp) / "events.sqlite3"
            con = sqlite3.connect(str(db))
            con.row_factory = sqlite3.Row
            try:
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS events(
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      ts TEXT NOT NULL,
                      event_type TEXT NOT NULL,
                      entity_type TEXT NOT NULL,
                      entity_id INTEGER NOT NULL,
                      payload_json TEXT NOT NULL,
                      prev_hash TEXT NOT NULL,
                      hash TEXT NOT NULL UNIQUE
                    )
                    """
                )
                event_append("test_a", "test", 1, {"dummy": 1}, con=con)
                event_append("test_b", "test", 2, {"dummy": 2}, con=con)
                con.commit()
                rows = con.execute("SELECT * FROM events ORDER BY id ASC").fetchall()
            finally:
                con.close()
    else:
        try:
            from app.config import Config

            db_path = Path(Config.CORE_DB)
            if not db_path.exists():
                return CheckResult(
                    name="check_eventlog_chain",
                    ok=False,
                    severity="warn",
                    reason="events DB missing",
                    remediation="Run app once to initialize DB.",
                )
            uri = f"file:{db_path}?mode=ro"
            con = sqlite3.connect(uri, uri=True)
            con.row_factory = sqlite3.Row
            try:
                rows = con.execute(
                    "SELECT * FROM events ORDER BY id ASC LIMIT ?",
                    (max(1, int(runner.eventlog_limit)),),
                ).fetchall()
            finally:
                con.close()
        except Exception as exc:
            return CheckResult(
                name="check_eventlog_chain",
                ok=False,
                severity="warn",
                reason=f"Could not verify chain: {exc}",
                remediation="DB may be empty/uninitialized.",
            )

    prev = "0" * 64
    for row in rows:
        rid = int(row["id"])
        prev_hash = str(row["prev_hash"] or "")
        if prev_hash != prev:
            return CheckResult(
                name="check_eventlog_chain",
                ok=False,
                severity="fail",
                reason=f"Chain broken (first bad: {rid})",
                details={"first_bad": rid, "reason": "prev_hash_mismatch"},
            )
        calc = event_hash(
            prev_hash,
            str(row["ts"] or ""),
            str(row["event_type"] or ""),
            str(row["entity_type"] or ""),
            int(row["entity_id"] or 0),
            str(row["payload_json"] or ""),
        )
        if calc != str(row["hash"] or ""):
            return CheckResult(
                name="check_eventlog_chain",
                ok=False,
                severity="fail",
                reason=f"Chain broken (first bad: {rid})",
                details={"first_bad": rid, "reason": "hash_mismatch"},
            )
        prev = str(row["hash"])

    return CheckResult(name="check_eventlog_chain", ok=True, severity="ok")


def check_crm_tables(runner) -> CheckResult:
    try:
        from app.config import Config

        if runner.mode == "ci":
            import kukanilea_core_v3_fixed as core

            with tempfile.TemporaryDirectory(prefix="kuka_health_crm_") as tmp:
                old_db = core.DB_PATH
                old_base = core.BASE_PATH
                old_eingang = core.EINGANG
                old_pending = core.PENDING_DIR
                old_done = core.DONE_DIR
                try:
                    t = Path(tmp)
                    core.DB_PATH = t / "core.db"
                    core.BASE_PATH = t / "base"
                    core.EINGANG = t / "eingang"
                    core.PENDING_DIR = t / "pending"
                    core.DONE_DIR = t / "done"
                    core.db_init()
                    con = sqlite3.connect(str(core.DB_PATH))
                    con.row_factory = sqlite3.Row
                    try:
                        must_tables = {
                            "customers",
                            "contacts",
                            "deals",
                            "quotes",
                            "quote_items",
                            "emails_cache",
                        }
                        rows = con.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                        got = {str(r[0]) for r in rows}
                        miss = sorted(must_tables - got)
                        if miss:
                            return CheckResult(
                                name="check_crm_tables",
                                ok=False,
                                severity="fail",
                                reason=f"missing tables: {miss}",
                            )
                    finally:
                        con.close()
                finally:
                    core.DB_PATH = old_db
                    core.BASE_PATH = old_base
                    core.EINGANG = old_eingang
                    core.PENDING_DIR = old_pending
                    core.DONE_DIR = old_done
            return CheckResult(name="check_crm_tables", ok=True, severity="ok")

        db_path = Path(Config.CORE_DB)
        if not db_path.exists():
            return CheckResult(
                name="check_crm_tables",
                ok=False,
                severity="warn",
                reason="CORE_DB missing",
                remediation="Run app once to initialize DB.",
            )
        uri = f"file:{db_path}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        con.row_factory = sqlite3.Row
        try:
            must_tables = {
                "customers",
                "contacts",
                "deals",
                "quotes",
                "quote_items",
                "emails_cache",
            }
            rows = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            got = {str(r[0]) for r in rows}
            miss = sorted(must_tables - got)
            if miss:
                return CheckResult(
                    name="check_crm_tables",
                    ok=False,
                    severity="fail",
                    reason=f"missing tables: {miss}",
                )
            return CheckResult(name="check_crm_tables", ok=True, severity="ok")
        finally:
            con.close()
    except Exception as exc:
        return CheckResult(
            name="check_crm_tables",
            ok=False,
            severity="fail",
            reason=f"crm table check failed: {exc}",
        )


def check_email_import_limits(runner) -> CheckResult:
    del runner
    try:
        from app.config import Config

        limit = int(getattr(Config, "MAX_EML_BYTES", 0) or 0)
        if limit <= 0:
            return CheckResult(
                name="check_email_import_limits",
                ok=False,
                severity="fail",
                reason="MAX_EML_BYTES must be > 0",
                remediation="Set KUKA_MAX_EML_BYTES to a sane value, e.g. 10485760.",
            )
        if limit > 50 * 1024 * 1024:
            return CheckResult(
                name="check_email_import_limits",
                ok=False,
                severity="warn",
                reason="MAX_EML_BYTES unusually high",
                remediation="Consider lowering KUKA_MAX_EML_BYTES for safety.",
                details={"max_eml_bytes": limit},
            )
        return CheckResult(
            name="check_email_import_limits",
            ok=True,
            severity="ok",
            details={"max_eml_bytes": limit},
        )
    except Exception as exc:
        return CheckResult(
            name="check_email_import_limits",
            ok=False,
            severity="fail",
            reason=f"config error: {exc}",
        )


def check_skills_registry(runner) -> CheckResult:
    if runner.mode == "ci":
        import app.skills.registry as registry

        ok = hasattr(registry, "register_skill") and hasattr(registry, "list_skills")
        return CheckResult(
            name="check_skills_registry",
            ok=ok,
            severity="ok" if ok else "fail",
            reason=None if ok else "skills registry API missing",
        )

    try:
        from app.config import Config

        root = Path(Config.USER_DATA_ROOT) / "skills"
        cache = root / "cache"
        quarantine = root / "quarantine"
        active = root / "active"
        missing = [_mask_path(p) for p in [cache, quarantine, active] if not p.exists()]
        if missing:
            return CheckResult(
                name="check_skills_registry",
                ok=False,
                severity="warn",
                reason="missing directories: " + ", ".join(missing),
                remediation="Directories are created on first skill operation.",
                details={"missing": missing},
            )

        import app.skills.registry as registry

        if not hasattr(registry, "list_skills"):
            return CheckResult(
                name="check_skills_registry",
                ok=False,
                severity="fail",
                reason="skills registry load failed",
            )
        return CheckResult(name="check_skills_registry", ok=True, severity="ok")
    except Exception as exc:
        return CheckResult(
            name="check_skills_registry",
            ok=False,
            severity="fail",
            reason=f"Skills registry error: {exc}",
            remediation="Check app/skills integrity.",
        )


def check_bench_baseline(runner) -> CheckResult:
    del runner
    baseline_path = Path("app/bench/baseline.json")
    if not baseline_path.exists():
        return CheckResult(
            name="check_bench_baseline",
            ok=False,
            severity="warn",
            reason="baseline.json missing",
            remediation="Run `python -m app.devtools.triage --bench --write-baseline`.",
        )
    try:
        payload = json.loads(baseline_path.read_text())
        size = len(payload.get("metrics", payload)) if isinstance(payload, dict) else 0
        return CheckResult(
            name="check_bench_baseline",
            ok=True,
            severity="ok",
            details={"metrics_count": int(size)},
        )
    except Exception as exc:
        return CheckResult(
            name="check_bench_baseline",
            ok=False,
            severity="fail",
            reason=f"Could not parse baseline: {exc}",
            remediation="Fix or regenerate baseline.json.",
        )


def check_web_routes_smoke(runner) -> CheckResult:
    del runner
    try:
        import app.web as web

        has_entry = any(
            hasattr(web, attr)
            for attr in ("bp", "app", "create_app", "register_routes")
        )
        if not has_entry:
            return CheckResult(
                name="check_web_routes_smoke",
                ok=False,
                severity="fail",
                reason="Could not find route entrypoint in app.web",
                remediation="Expose blueprint/app factory symbols in app/web.py.",
            )
        return CheckResult(name="check_web_routes_smoke", ok=True, severity="ok")
    except Exception as exc:
        return CheckResult(
            name="check_web_routes_smoke",
            ok=False,
            severity="fail",
            reason=f"Could not import web routes: {exc}",
            remediation="Check app/web.py import graph and route registration.",
        )


def check_ai_gate_smoke(runner) -> CheckResult:
    if runner.mode != "ci":
        return CheckResult(
            name="check_ai_gate_smoke",
            ok=True,
            severity="ok",
            details={"skipped": True},
        )

    if os.environ.get("KUKA_AI_ENABLE", ""):
        return CheckResult(
            name="check_ai_gate_smoke",
            ok=True,
            severity="ok",
            details={"note": "KUKA_AI_ENABLE set, skip negative gate"},
        )

    before = {m for m in sys.modules if m.startswith(_HEAVY_PREFIXES)}
    for mod in list(before):
        if mod.startswith(("chromadb", "sentence_transformers", "ollama")):
            sys.modules.pop(mod, None)

    import app.ai  # noqa: F401
    import app.ai.knowledge  # noqa: F401

    after = {m for m in sys.modules if m.startswith(_HEAVY_PREFIXES)}
    leaked = sorted(after - before)
    if leaked:
        return CheckResult(
            name="check_ai_gate_smoke",
            ok=False,
            severity="fail",
            reason=f"Unexpected imports: {leaked}",
            remediation="Use lazy imports behind KUKA_AI_ENABLE gate.",
        )
    return CheckResult(name="check_ai_gate_smoke", ok=True, severity="ok")
