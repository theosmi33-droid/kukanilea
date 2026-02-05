from __future__ import annotations

import os
from pathlib import Path


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    PORT = int(_env("PORT", "5051"))
    SECRET_KEY = _env("KUKANILEA_SECRET", "kukanilea-dev-secret-change-me")
    MAX_CONTENT_LENGTH = int(_env("KUKANILEA_MAX_UPLOAD", str(25 * 1024 * 1024)))
    AUTH_DB = Path(_env("KUKANILEA_AUTH_DB", str(Path(__file__).resolve().parent.parent / "instance" / "kukanilea.db")))
    CORE_DB = Path(_env("DB_FILENAME", str(Path.home() / "Tophandwerk_DB.sqlite3")))
    TENANT_DEFAULT = _env("TENANT_DEFAULT", "KUKANILEA")
    TENANT_FIXED = _env("TENANT_FIXED", "1") not in ("0", "false", "False", "no", "NO")
    FEATURE_GOOGLE_OAUTH = _env("FEATURE_GOOGLE_OAUTH", "0") == "1"
    GOOGLE_CLIENT_ID = _env("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = _env("GOOGLE_CLIENT_SECRET", "")
