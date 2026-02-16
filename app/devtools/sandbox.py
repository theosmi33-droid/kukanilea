from __future__ import annotations

import hashlib
import shutil
import sqlite3
import tempfile
from pathlib import Path


def _resolve_config_object():
    import app.config as config_module

    for name in ("Config", "Settings", "AppConfig"):
        candidate = getattr(config_module, name, None)
        if candidate is not None and hasattr(candidate, "CORE_DB"):
            return candidate
    if hasattr(config_module, "CORE_DB"):
        return config_module
    raise RuntimeError("config_core_db_missing")


def resolve_core_db_path() -> Path:
    cfg = _resolve_config_object()
    return Path(str(getattr(cfg, "CORE_DB")))


def _copy_db_with_sidecars(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copy2(src, dst)
        for suffix in ("-wal", "-shm"):
            extra_src = Path(str(src) + suffix)
            extra_dst = Path(str(dst) + suffix)
            if extra_src.exists():
                shutil.copy2(extra_src, extra_dst)
        return
    con = sqlite3.connect(str(dst))
    con.close()


def create_sandbox_copy(tenant_id: str) -> tuple[Path, Path]:
    _ = str(tenant_id or "").strip()  # explicit input normalization for call symmetry
    real_core_db = resolve_core_db_path()
    sandbox_dir = Path(tempfile.mkdtemp(prefix="kukanilea-ocr-sandbox-"))
    sandbox_db = sandbox_dir / "core.sqlite3"
    _copy_db_with_sidecars(real_core_db, sandbox_db)
    return sandbox_db, sandbox_dir


def cleanup_sandbox(sandbox_dir: Path) -> None:
    shutil.rmtree(sandbox_dir, ignore_errors=True)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
