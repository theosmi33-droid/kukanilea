from __future__ import annotations

import os
import platform
import secrets
from pathlib import Path

try:
    from platformdirs import user_data_dir
except Exception:  # pragma: no cover

    def user_data_dir(appname: str, appauthor: bool = False) -> str:
        if platform.system() == "Windows":
            return str(Path.home() / "AppData" / "Local" / appname)
        return str(Path.home() / "Library" / "Application Support" / appname)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _is_dev_env() -> bool:
    env = _env("KUKANILEA_ENV", _env("FLASK_ENV", "")).strip().lower()
    if env in {"dev", "development", "local", "test", "testing"}:
        return True
    # pytest workers should never be blocked by production-only secret checks.
    if _env("PYTEST_CURRENT_TEST"):
        return True
    return False


def _resolve_secret_key() -> str:
    key = _env("KUKANILEA_SECRET", "").strip()
    if key:
        return key

    env = _env("KUKANILEA_ENV", _env("FLASK_ENV", "")).strip().lower()
    if not env:
        # Backward-compatible fallback for local runs where environment isn't explicitly set.
        return f"kukanilea-dev-{secrets.token_urlsafe(24)}"

    if _is_dev_env():
        # Stable enough for local/dev convenience while avoiding a shared static secret.
        return f"kukanilea-dev-{secrets.token_urlsafe(24)}"

    raise RuntimeError(
        "KUKANILEA_SECRET is required outside development/test environments. "
        "Set KUKANILEA_SECRET to a strong random value."
    )


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    PORT = int(_env("PORT", "5051"))
    SECRET_KEY = _resolve_secret_key()
    MAX_CONTENT_LENGTH = int(_env("KUKANILEA_MAX_UPLOAD", str(100 * 1024 * 1024)))

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
    TRIAL_DAYS = int(_env("KUKANILEA_TRIAL_DAYS", "14"))

    IMPORT_ROOT = Path(_env("IMPORT_ROOT", str(USER_DATA_ROOT / "imports")))
    IMPORT_ROOT.mkdir(parents=True, exist_ok=True)

    ZWISCHENABLAGE = USER_DATA_ROOT / "zwischenablage"
    ZWISCHENABLAGE.mkdir(parents=True, exist_ok=True)

    TENANT_DEFAULT = _env("TENANT_DEFAULT", "KUKANILEA")
    TENANT_FIXED = _env("TENANT_FIXED", "1") not in ("0", "false", "False", "no", "NO")

    KUK_HEALER_ENABLED = _env("KUK_HEALER_ENABLED", "0") == "1"
    KUK_OTEL_ENABLED = _env("KUK_OTEL_ENABLED", "0") == "1"
    KUK_DIAG_ENABLED = _env("KUK_DIAG_ENABLED", "0") == "1"

    SESSION_IDLE_TIMEOUT_SECONDS = int(_env("KUKANILEA_SESSION_IDLE_TIMEOUT_SECONDS", "3600"))
    SESSION_ABSOLUTE_TIMEOUT_SECONDS = int(_env("KUKANILEA_SESSION_ABSOLUTE_TIMEOUT_SECONDS", str(8 * 3600)))
    CORS_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in _env("KUKANILEA_CORS_ALLOWED_ORIGINS", "http://localhost:5051").split(",")
        if origin.strip()
    ]

    # Lexoffice Integration
    LEXOFFICE_API_KEY = _env("LEXOFFICE_API_KEY", "")

    # White-Labeling / Branding
    BRANDING_FILE = USER_DATA_ROOT / "branding.json"

    @classmethod
    def get_branding(cls):
        defaults = {
            "app_name": "KUKANILEA",
            "primary_color": "#2563eb",  # blue-600
            "logo_url": "/static/logo.png",
            "support_url": "https://kukanilea.de",
            "footer_text": "KUKANILEA — Lokale Intelligenz fürs Handwerk",
        }
        if cls.BRANDING_FILE.exists():
            import json

            try:
                with open(cls.BRANDING_FILE, "r") as f:
                    custom = json.load(f)
                    defaults.update(custom)
            except Exception:
                pass
        return defaults
