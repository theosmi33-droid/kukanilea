from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

try:
    from platformdirs import user_data_dir
except Exception:  # pragma: no cover - fallback when dependency not installed

    def user_data_dir(appname: str, appauthor: bool = False) -> str:
        return str(Path.home() / "Library" / "Application Support" / appname)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def get_data_dir() -> Path:
    root = _env("KUKANILEA_USER_DATA_ROOT", "")
    if root.strip():
        path = Path(root).expanduser()
    else:
        path = Path(user_data_dir("KUKANILEA", appauthor=False))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        for parent in exe.parents:
            if parent.suffix.lower() == ".app":
                return parent
        return exe.parent
    return Path(__file__).resolve().parent.parent


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    PORT = int(_env("PORT", "5051"))
    SECRET_KEY = _env("KUKANILEA_SECRET", "kukanilea-dev-secret-change-me")
    THEME_DEFAULT = _env("KUKANILEA_THEME_DEFAULT", "light").strip().lower() or "light"
    MAX_CONTENT_LENGTH = int(_env("KUKANILEA_MAX_UPLOAD", str(25 * 1024 * 1024)))
    MAX_EML_BYTES = int(_env("KUKA_MAX_EML_BYTES", str(10 * 1024 * 1024)))

    USER_DATA_ROOT = get_data_dir()
    USER_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    APP_DIR = get_app_dir()

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
    LICENSE_VALIDATE_URL = _env(
        "KUKANILEA_LICENSE_VALIDATE_URL", _env("LICENSE_SERVER_URL", "")
    )
    LICENSE_VALIDATE_TIMEOUT_SECONDS = int(
        _env("KUKANILEA_LICENSE_VALIDATE_TIMEOUT_SECONDS", "10")
    )
    LICENSE_VALIDATE_INTERVAL_DAYS = int(
        _env("KUKANILEA_LICENSE_VALIDATE_INTERVAL_DAYS", "30")
    )
    LICENSE_GRACE_DAYS = int(_env("KUKANILEA_LICENSE_GRACE_DAYS", "30"))

    IMPORT_ROOT = Path(_env("IMPORT_ROOT", str(USER_DATA_ROOT / "imports")))
    IMPORT_ROOT.mkdir(parents=True, exist_ok=True)

    TENANT_DEFAULT = _env(
        "KUKANILEA_FIXED_TENANT_ID", _env("TENANT_DEFAULT", "KUKANILEA")
    )
    TENANT_NAME = _env("KUKANILEA_TENANT_NAME", TENANT_DEFAULT)
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
    OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL = _env("OLLAMA_MODEL", "llama3.1:8b")
    OLLAMA_MODEL_FALLBACKS = _env(
        "KUKANILEA_OLLAMA_MODEL_FALLBACKS", "llama3.2:3b,qwen2.5:3b"
    )
    OLLAMA_TIMEOUT = int(_env("OLLAMA_TIMEOUT", "300"))
    OLLAMA_AUTOSTART = _env("KUKANILEA_OLLAMA_AUTOSTART", "1") in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
        "on",
        "ON",
    )
    OLLAMA_AUTOSTART_TIMEOUT_SECONDS = int(
        _env("KUKANILEA_OLLAMA_AUTOSTART_TIMEOUT_SECONDS", "20")
    )
    AI_BOOTSTRAP_ON_FIRST_RUN = _env("KUKANILEA_AI_BOOTSTRAP_ON_FIRST_RUN", "1") in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
        "on",
        "ON",
    )
    AI_BOOTSTRAP_PULL_MODELS = _env("KUKANILEA_AI_BOOTSTRAP_PULL_MODELS", "1") in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
        "on",
        "ON",
    )
    AI_BOOTSTRAP_MODEL_LIST = _env("KUKANILEA_AI_BOOTSTRAP_MODEL_LIST", "")
    AI_BOOTSTRAP_MODEL_PULL_TIMEOUT_SECONDS = int(
        _env("KUKANILEA_AI_BOOTSTRAP_MODEL_PULL_TIMEOUT_SECONDS", "1800")
    )
    AI_BOOTSTRAP_USE_MODELPACK = _env("KUKANILEA_AI_BOOTSTRAP_USE_MODELPACK", "1") in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
        "on",
        "ON",
    )
    AI_BOOTSTRAP_MODELPACK_FILE = Path(
        _env(
            "KUKANILEA_AI_BOOTSTRAP_MODELPACK_FILE",
            str(USER_DATA_ROOT / "modelpacks" / "ollama-modelpack.tar.gz"),
        )
    )
    AI_BOOTSTRAP_MODELPACK_EXPORT_DIR = Path(
        _env(
            "KUKANILEA_AI_BOOTSTRAP_MODELPACK_EXPORT_DIR",
            str(USER_DATA_ROOT / "modelpacks"),
        )
    )
    AI_BOOTSTRAP_STATE_FILE = Path(
        _env(
            "KUKANILEA_AI_BOOTSTRAP_STATE_FILE",
            str(USER_DATA_ROOT / "ai_bootstrap_state.json"),
        )
    )
    AI_MEMORY_DB = Path(
        _env("KUKANILEA_AI_MEMORY_DB", str(USER_DATA_ROOT / "ai_memory.sqlite3"))
    )
    AI_PROVIDER_ORDER = _env("KUKANILEA_AI_PROVIDER_ORDER", "ollama")
    AI_PROVIDERS_JSON = _env("KUKANILEA_AI_PROVIDERS_JSON", "")
    AI_PROVIDER_RETRIES = int(_env("KUKANILEA_AI_PROVIDER_RETRIES", "1"))
    AI_HEALTH_TTL_SECONDS = int(_env("KUKANILEA_AI_HEALTH_TTL_SECONDS", "30"))
    VLLM_BASE_URL = _env("KUKANILEA_VLLM_BASE_URL", "http://127.0.0.1:8000")
    VLLM_MODEL = _env("KUKANILEA_VLLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    VLLM_API_KEY = _env("KUKANILEA_VLLM_API_KEY", "")
    VLLM_TIMEOUT = int(_env("KUKANILEA_VLLM_TIMEOUT", "60"))
    LMSTUDIO_BASE_URL = _env("KUKANILEA_LMSTUDIO_BASE_URL", "http://127.0.0.1:1234")
    LMSTUDIO_MODEL = _env("KUKANILEA_LMSTUDIO_MODEL", "local-model")
    LMSTUDIO_TIMEOUT = int(_env("KUKANILEA_LMSTUDIO_TIMEOUT", "60"))
    GROQ_BASE_URL = _env("KUKANILEA_GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    GROQ_MODEL = _env("KUKANILEA_GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_API_KEY = _env("KUKANILEA_GROQ_API_KEY", _env("GROQ_API_KEY", ""))
    GROQ_TIMEOUT = int(_env("KUKANILEA_GROQ_TIMEOUT", "30"))
    ANTHROPIC_BASE_URL = _env(
        "KUKANILEA_ANTHROPIC_BASE_URL", "https://api.anthropic.com"
    )
    ANTHROPIC_MODEL = _env("KUKANILEA_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    ANTHROPIC_API_KEY = _env(
        "KUKANILEA_ANTHROPIC_API_KEY", _env("ANTHROPIC_API_KEY", "")
    )
    ANTHROPIC_TIMEOUT = int(_env("KUKANILEA_ANTHROPIC_TIMEOUT", "60"))
    GEMINI_BASE_URL = _env(
        "KUKANILEA_GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"
    )
    GEMINI_MODEL = _env("KUKANILEA_GEMINI_MODEL", "gemini-1.5-flash")
    GEMINI_API_KEY = _env(
        "KUKANILEA_GEMINI_API_KEY",
        _env("GEMINI_API_KEY", _env("GOOGLE_API_KEY", "")),
    )
    GEMINI_TIMEOUT = int(_env("KUKANILEA_GEMINI_TIMEOUT", "60"))
    MAIL_MODE = _env("MAIL_MODE", "outbox").strip().lower() or "outbox"
    DEV_LOCAL_EMAIL_CODES = _env("DEV_LOCAL_EMAIL_CODES", "0") in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    )
    UPDATE_CHECK_ENABLED = _env("KUKANILEA_UPDATE_CHECK_ENABLED", "0") in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    )
    UPDATE_CHECK_URL = _env(
        "KUKANILEA_UPDATE_CHECK_URL",
        "https://api.github.com/repos/theosmi33-droid/kukanilea/releases/latest",
    )
    UPDATE_CHECK_TIMEOUT_SECONDS = int(
        _env("KUKANILEA_UPDATE_CHECK_TIMEOUT_SECONDS", "5")
    )
    UPDATE_INSTALL_ENABLED = _env("KUKANILEA_UPDATE_INSTALL_ENABLED", "0") in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    )
    UPDATE_INSTALL_URL = _env("KUKANILEA_UPDATE_INSTALL_URL", UPDATE_CHECK_URL)
    UPDATE_INSTALL_TIMEOUT_SECONDS = int(
        _env("KUKANILEA_UPDATE_INSTALL_TIMEOUT_SECONDS", "30")
    )
    UPDATE_MANIFEST_URL = _env("KUKANILEA_UPDATE_MANIFEST_URL", "")
    UPDATE_SIGNING_REQUIRED = _env("KUKANILEA_UPDATE_SIGNING_REQUIRED", "0") in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    )
    UPDATE_SIGNING_PUBLIC_KEY = _env("KUKANILEA_UPDATE_SIGNING_PUBLIC_KEY", "")
    UPDATE_SIGNING_PUBLIC_KEY_FILE = _env(
        "KUKANILEA_UPDATE_SIGNING_PUBLIC_KEY_FILE", ""
    )
    UPDATE_APP_DIR = Path(_env("KUKANILEA_UPDATE_APP_DIR", str(APP_DIR)))
    UPDATE_DOWNLOAD_DIR = Path(
        _env("KUKANILEA_UPDATE_DOWNLOAD_DIR", str(USER_DATA_ROOT / "updates"))
    )
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(_env("KUKANILEA_SESSION_ABSOLUTE_TIMEOUT_HOURS", "8"))
    )
    SESSION_REFRESH_EACH_REQUEST = False
    SESSION_IDLE_TIMEOUT_DEFAULT_MINUTES = int(
        _env("KUKANILEA_IDLE_TIMEOUT_DEFAULT_MINUTES", "60")
    )
    SESSION_IDLE_TIMEOUT_MIN_MINUTES = int(
        _env("KUKANILEA_IDLE_TIMEOUT_MIN_MINUTES", "15")
    )
    SESSION_IDLE_TIMEOUT_MAX_MINUTES = int(
        _env("KUKANILEA_IDLE_TIMEOUT_MAX_MINUTES", "480")
    )
    SESSION_IDLE_TOUCH_SECONDS = int(_env("KUKANILEA_IDLE_TOUCH_SECONDS", "60"))
    UI_HEALTH_POLL_MS = int(_env("KUKANILEA_UI_HEALTH_POLL_MS", "60000"))
    UI_STATUS_POLL_MS = int(_env("KUKANILEA_UI_STATUS_POLL_MS", "15000"))
    UI_AI_STATUS_CLIENT_CACHE_MS = int(
        _env("KUKANILEA_UI_AI_STATUS_CLIENT_CACHE_MS", "45000")
    )
    AI_STATUS_CACHE_TTL_SECONDS = int(
        _env("KUKANILEA_AI_STATUS_CACHE_TTL_SECONDS", "15")
    )
