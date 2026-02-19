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
    result: dict[str, Any] = {
        "checked": False,
        "update_available": False,
        "latest_version": "",
        "download_url": "",
        "error": "",
    }

    url = str(release_url or "").strip()
    if not url:
        result["error"] = "release_url_missing"
        return result

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "KUKANILEA-UpdateChecker/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=max(1, int(timeout_seconds))) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        result["error"] = f"http_{int(getattr(exc, 'code', 0) or 0)}"
        return result
    except Exception:
        result["error"] = "request_failed"
        return result

    if not isinstance(payload, dict):
        result["error"] = "invalid_payload"
        return result

    latest_raw = str(payload.get("tag_name") or payload.get("name") or "").strip()
    latest = latest_raw.lstrip("v")
    html_url = str(payload.get("html_url") or "").strip()

    if not latest:
        result["error"] = "missing_version"
        return result

    result["checked"] = True
    result["latest_version"] = latest
    result["download_url"] = html_url
    result["update_available"] = is_newer_version(latest, current_version)
    return result
