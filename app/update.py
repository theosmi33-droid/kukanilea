from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .update_checker import DEFAULT_RELEASE_URL, is_newer_version

try:
    from platformdirs import user_data_dir
except Exception:  # pragma: no cover - fallback when dependency not installed

    def user_data_dir(appname: str, appauthor: bool = False) -> str:
        return str(Path.home() / "Library" / "Application Support" / appname)


class UpdateError(RuntimeError):
    def __init__(self, message: str, *, code: str = "update_error") -> None:
        super().__init__(message)
        self.code = code


def _now_tag() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "")
    )


def get_data_dir() -> Path:
    root = os.environ.get("KUKANILEA_USER_DATA_ROOT", "").strip()
    if root:
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
    return Path(__file__).resolve().parents[1]


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _request_json(url: str, *, timeout_seconds: int) -> dict[str, Any]:
    req = urllib.request.Request(
        str(url),
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "KUKANILEA-Updater/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(1, int(timeout_seconds))) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raise UpdateError(
            f"Release-Metadaten konnten nicht geladen werden (HTTP {int(exc.code or 0)}).",
            code=f"http_{int(exc.code or 0)}",
        ) from exc
    except Exception as exc:
        raise UpdateError(
            "Release-Metadaten konnten nicht geladen werden.", code="request_failed"
        ) from exc
    if not isinstance(payload, dict):
        raise UpdateError("Release-Metadaten sind ungültig.", code="invalid_payload")
    return payload


def _request_text(url: str, *, timeout_seconds: int) -> str:
    req = urllib.request.Request(
        str(url),
        headers={"User-Agent": "KUKANILEA-Updater/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(1, int(timeout_seconds))) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise UpdateError(
            "SHA256-Datei konnte nicht geladen werden.", code="sha_fetch"
        ) from exc


def _extract_sha256_from_text(text: str) -> str:
    for token in str(text or "").replace("\n", " ").split():
        value = token.strip().lower()
        if len(value) == 64 and all(ch in "0123456789abcdef" for ch in value):
            return value
    return ""


def _coerce_assets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("assets")
    if not isinstance(raw, list):
        return []
    return [a for a in raw if isinstance(a, dict)]


def _pick_zip_asset(
    assets: list[dict[str, Any]],
    *,
    platform_name: str,
) -> dict[str, Any] | None:
    zip_assets: list[dict[str, Any]] = []
    for asset in assets:
        name = str(asset.get("name") or "").strip()
        if name.lower().endswith(".zip"):
            zip_assets.append(asset)
    if not zip_assets:
        return None

    token_map = {
        "darwin": ("darwin", "mac", "osx"),
        "win32": ("win", "windows"),
        "linux": ("linux",),
    }
    tokens = token_map.get(platform_name, ())
    for asset in zip_assets:
        name = str(asset.get("name") or "").lower()
        if any(token in name for token in tokens):
            return asset
    return zip_assets[0]


def check_for_installable_update(
    current_version: str,
    *,
    release_url: str = DEFAULT_RELEASE_URL,
    timeout_seconds: int = 10,
    platform_name: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "checked": False,
        "update_available": False,
        "latest_version": "",
        "release_url": "",
        "asset_name": "",
        "asset_url": "",
        "sha256": "",
        "error": "",
    }
    payload = _request_json(release_url, timeout_seconds=timeout_seconds)
    latest_raw = str(payload.get("tag_name") or payload.get("name") or "").strip()
    latest = latest_raw.lstrip("v")
    if not latest:
        result["error"] = "missing_version"
        return result

    result["checked"] = True
    result["latest_version"] = latest
    result["release_url"] = str(payload.get("html_url") or "").strip()

    if not is_newer_version(latest, current_version):
        return result
    result["update_available"] = True

    assets = _coerce_assets(payload)
    selected = _pick_zip_asset(assets, platform_name=(platform_name or sys.platform))
    if not selected:
        result["error"] = "install_asset_missing"
        return result

    name = str(selected.get("name") or "").strip()
    url = str(selected.get("browser_download_url") or "").strip()
    if not name or not url:
        result["error"] = "install_asset_invalid"
        return result
    result["asset_name"] = name
    result["asset_url"] = url

    digest = str(selected.get("digest") or "").strip().lower()
    if digest.startswith("sha256:"):
        result["sha256"] = digest.split(":", 1)[1].strip()
        return result

    # Optional fallback: companion .sha256 asset.
    expected_names = {f"{name}.sha256", f"{name.rsplit('.', 1)[0]}.sha256"}
    for asset in assets:
        asset_name = str(asset.get("name") or "").strip()
        if asset_name not in expected_names:
            continue
        sha_url = str(asset.get("browser_download_url") or "").strip()
        if not sha_url:
            continue
        text = _request_text(sha_url, timeout_seconds=timeout_seconds)
        parsed = _extract_sha256_from_text(text)
        if parsed:
            result["sha256"] = parsed
            break
    return result


def download_update_asset(
    asset_url: str,
    *,
    download_dir: Path,
    timeout_seconds: int = 30,
) -> Path:
    url = str(asset_url or "").strip()
    if not url:
        raise UpdateError("Download-URL fehlt.", code="asset_url_missing")
    download_dir.mkdir(parents=True, exist_ok=True)
    parsed = urllib.parse.urlparse(url)
    filename = Path(parsed.path).name or "kukanilea_update.zip"
    target = download_dir / filename
    partial = download_dir / f"{filename}.part"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "KUKANILEA-Updater/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(1, int(timeout_seconds))) as resp:
            with partial.open("wb") as fh:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
    except Exception as exc:
        try:
            partial.unlink(missing_ok=True)
        except Exception:
            pass
        raise UpdateError(
            "Update-Download fehlgeschlagen.", code="download_failed"
        ) from exc
    partial.replace(target)
    return target


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _find_payload_root(extract_dir: Path, app_dir: Path) -> Path:
    exact = extract_dir / app_dir.name
    if exact.exists():
        return exact
    app_candidates = [p for p in extract_dir.glob("*.app") if p.is_dir()]
    if app_candidates:
        return app_candidates[0]
    dirs = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(dirs) == 1:
        return dirs[0]
    raise UpdateError(
        "Update-Paket enthält kein installierbares App-Verzeichnis.",
        code="payload_missing",
    )


def install_update_from_archive(
    archive_path: Path,
    *,
    app_dir: Path,
    data_dir: Path,
    expected_sha256: str = "",
) -> dict[str, str]:
    archive = Path(archive_path)
    target = Path(app_dir)
    storage = Path(data_dir)

    if not archive.exists():
        raise UpdateError("Update-Archiv nicht gefunden.", code="archive_missing")
    if archive.suffix.lower() != ".zip":
        raise UpdateError("Nur ZIP-Updates werden unterstützt.", code="archive_type")
    if not target.exists():
        raise UpdateError("Installationsziel existiert nicht.", code="app_dir_missing")

    checksum = compute_sha256(archive)
    wanted = str(expected_sha256 or "").strip().lower()
    if wanted and checksum.lower() != wanted:
        raise UpdateError("SHA256-Prüfung fehlgeschlagen.", code="sha_mismatch")

    stage_parent = target.parent
    stage_dir = Path(
        tempfile.mkdtemp(prefix="kukanilea-update-", dir=str(stage_parent))
    ).resolve()
    backup_dir = target.parent / f"{target.name}.backup"
    try:
        with zipfile.ZipFile(str(archive), "r") as zf:
            zf.extractall(stage_dir)
        payload = _find_payload_root(stage_dir, target)

        _remove_path(backup_dir)
        shutil.move(str(target), str(backup_dir))
        try:
            shutil.move(str(payload), str(target))
        except Exception as exc:
            # rollback immediately
            if backup_dir.exists():
                _remove_path(target)
                shutil.move(str(backup_dir), str(target))
            raise UpdateError(
                "Update-Installation fehlgeschlagen; Rollback wurde ausgeführt.",
                code="install_failed",
            ) from exc
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)

    return {
        "app_dir": str(target),
        "backup_dir": str(backup_dir),
        "data_dir": str(storage),
        "sha256": checksum,
    }


def rollback_update(*, app_dir: Path) -> dict[str, str]:
    target = Path(app_dir)
    backup_dir = target.parent / f"{target.name}.backup"
    if not backup_dir.exists():
        raise UpdateError("Kein Rollback-Backup vorhanden.", code="rollback_missing")

    if target.exists():
        failed = target.parent / f"{target.name}.failed-{_now_tag()}"
        shutil.move(str(target), str(failed))
    else:
        failed = Path("")
    shutil.move(str(backup_dir), str(target))
    return {
        "app_dir": str(target),
        "restored_from": str(backup_dir),
        "failed_dir": str(failed),
    }
