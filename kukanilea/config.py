from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class AppConfig:
    base_dir: Path
    secret_key: str
    auth_db: Path
    core_db: Path
    tenant_default: str
    tenant_fixed: bool
    max_upload_bytes: int
    feature_google_oauth: bool
    google_client_id: str
    google_client_secret: str


def load_config() -> AppConfig:
    base_dir = Path(__file__).resolve().parents[1]
    return AppConfig(
        base_dir=base_dir,
        secret_key=_env("KUKANILEA_SECRET", "kukanilea-dev-secret-change-me"),
        auth_db=Path(
            _env(
                "KUKANILEA_AUTH_DB",
                str(base_dir / "instance" / "kukanilea.db"),
            )
        ),
        core_db=Path(_env("DB_FILENAME", str(Path.home() / "Tophandwerk_DB.sqlite3"))),
        tenant_default=_env("TENANT_DEFAULT", "KUKANILEA"),
        tenant_fixed=_env("TENANT_FIXED", "1") not in ("0", "false", "False", "no", "NO"),
        max_upload_bytes=int(_env("KUKANILEA_MAX_UPLOAD", str(25 * 1024 * 1024))),
        feature_google_oauth=_env("FEATURE_GOOGLE_OAUTH", "0") == "1",
        google_client_id=_env("GOOGLE_CLIENT_ID", ""),
        google_client_secret=_env("GOOGLE_CLIENT_SECRET", ""),
    )


def doctor_report() -> dict:
    config = load_config()
    return {
        "base_dir": str(config.base_dir),
        "auth_db": str(config.auth_db),
        "core_db": str(config.core_db),
        "tenant_default": config.tenant_default,
        "tenant_fixed": config.tenant_fixed,
        "max_upload_bytes": config.max_upload_bytes,
        "features": {"google_oauth": config.feature_google_oauth},
        "paths": {
            "auth_db_exists": config.auth_db.exists(),
            "core_db_exists": config.core_db.exists(),
        },
    }
