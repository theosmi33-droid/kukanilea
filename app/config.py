from __future__ import annotations

import os
from pathlib import Path

try:
    from platformdirs import user_data_dir
except Exception:  # pragma: no cover - fallback when dependency not installed

    def user_data_dir(appname: str, appauthor: bool = False) -> str:
        return str(Path.home() / "Library" / "Application Support" / appname)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    PORT = int(_env("PORT", "5051"))
    SECRET_KEY = _env("KUKANILEA_SECRET", "kukanilea-dev-secret-change-me")
    MAX_CONTENT_LENGTH = int(_env("KUKANILEA_MAX_UPLOAD", str(25 * 1024 * 1024)))
    MAX_EML_BYTES = int(_env("KUKA_MAX_EML_BYTES", str(10 * 1024 * 1024)))

    USER_DATA_ROOT = Path(
        _env(
            "KUKANILEA_USER_DATA_ROOT",
            user_data_dir("KUKANILEA", appauthor=False),
        )
    )
    USER_DATA_ROOT.mkdir(parents=True, exist_ok=True)

    LOG_DIR = USER_DATA_ROOT / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    AUTH_DB = Path(_env("KUKANILEA_AUTH_DB", str(USER_DATA_ROOT / "auth.sqlite3")))
    CORE_DB = Path(_env("KUKANILEA_CORE_DB", str(USER_DATA_ROOT / "core.sqlite3")))
    LICENSE_PATH = Path(
        _env("KUKANILEA_LICENSE_PATH", str(USER_DATA_ROOT / "license.json"))
    )
    TRIAL_PATH = Path(_env("KUKANILEA_TRIAL_PATH", str(USER_DATA_ROOT / "trial.json")))
    LICENSE_CACHE_PATH = Path(
        _env("KUKANILEA_LICENSE_CACHE_PATH", str(USER_DATA_ROOT / "license_cache.json"))
    )
    TRIAL_DAYS = int(_env("KUKANILEA_TRIAL_DAYS", "14"))
    LICENSE_VALIDATE_URL = _env("KUKANILEA_LICENSE_VALIDATE_URL", "")
    LICENSE_VALIDATE_TIMEOUT_SECONDS = int(
        _env("KUKANILEA_LICENSE_VALIDATE_TIMEOUT_SECONDS", "10")
    )
    LICENSE_VALIDATE_INTERVAL_DAYS = int(
        _env("KUKANILEA_LICENSE_VALIDATE_INTERVAL_DAYS", "30")
    )
    LICENSE_GRACE_DAYS = int(_env("KUKANILEA_LICENSE_GRACE_DAYS", "30"))

    IMPORT_ROOT = Path(_env("IMPORT_ROOT", str(USER_DATA_ROOT / "imports")))
    IMPORT_ROOT.mkdir(parents=True, exist_ok=True)

    TENANT_DEFAULT = _env("TENANT_DEFAULT", "KUKANILEA")
    TENANT_FIXED = _env("TENANT_FIXED", "1") not in ("0", "false", "False", "no", "NO")
    FEATURE_GOOGLE_OAUTH = _env("FEATURE_GOOGLE_OAUTH", "0") == "1"
    GOOGLE_CLIENT_ID = _env("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = _env("GOOGLE_CLIENT_SECRET", "")
    MICROSOFT_CLIENT_ID = _env("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET = _env("MICROSOFT_CLIENT_SECRET", "")
    OAUTH_REDIRECT_BASE = _env("OAUTH_REDIRECT_BASE", "")
    WEBHOOK_ALLOWED_DOMAINS = _env("WEBHOOK_ALLOWED_DOMAINS", "")
    WEBHOOK_ALLOWED_DOMAINS_LIST = [
        part.strip().lower()
        for part in WEBHOOK_ALLOWED_DOMAINS.split(",")
        if part.strip()
    ]
    AUTOMATION_CRON_ENABLED = _env("AUTOMATION_CRON_ENABLED", "1") == "1"
    AUTOMATION_CRON_INTERVAL_SECONDS = int(
        _env("AUTOMATION_CRON_INTERVAL_SECONDS", "60")
    )
