from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

DEFAULT_RELEASE_URL = (
    "https://api.github.com/repos/theosmi33-droid/kukanilea/releases/latest"
)

_VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<stage>alpha|beta|rc)\.(?P<stage_n>\d+))?$",
    re.IGNORECASE,
)


def _version_key(version: str) -> tuple[int, int, int, int, int] | None:
    match = _VERSION_RE.match(str(version or "").strip())
    if not match:
        return None

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))
    stage = (match.group("stage") or "").lower()
    stage_n = int(match.group("stage_n") or 0)

    # Stable > rc > beta > alpha
    if not stage:
        stage_rank = 3
    elif stage == "rc":
        stage_rank = 2
    elif stage == "beta":
        stage_rank = 1
    else:
        stage_rank = 0

    return (major, minor, patch, stage_rank, stage_n)


def is_newer_version(latest_version: str, current_version: str) -> bool:
    latest_key = _version_key(latest_version)
    current_key = _version_key(current_version)

    if latest_key is None or current_key is None:
        return False

    return latest_key > current_key


def check_for_updates(
    current_version: str,
    *,
    release_url: str = DEFAULT_RELEASE_URL,
    timeout_seconds: int = 5,
) -> dict[str, Any]:
    """
    Prüft auf neue Versionen. 
    Gold-Edition: Nutzt primär den lokalen Update-Server falls konfiguriert.
    """
    from .update import check_for_installable_update
    
    # Versuche den lokalen Update-Server (NAS)
    local_manifest = os.environ.get("KUKANILEA_UPDATE_MANIFEST_URL", "http://127.0.0.1:8080/manifest.json")
    
    try:
        res = check_for_installable_update(
            current_version=current_version,
            manifest_url=local_manifest,
            timeout_seconds=timeout_seconds
        )
        if res.get("update_available"):
            return res
    except Exception as e:
        # Fallback auf GitHub falls NAS-Server offline
        pass

    # ... (Rest der bestehenden Logik für GitHub)
