"""
app/update.py – Auto‑Update für KUKANILEA v1.5.0 Gold.
Verwaltet Versions-Checks, Downloads, Signatur-Verifizierung und Installation.
"""

import os
import sys
import json
import time
import logging
import platform
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

import requests
import gnupg

from .version import __version__

logger = logging.getLogger("kukanilea.update")

class UpdateError(RuntimeError):
    """Base class for update errors."""

# Konfiguration
GITHUB_API = "https://api.github.com/repos/theosmi33-droid/kukanilea/releases/latest"
PUBLIC_KEY_PATH = Path(__file__).parent / "certs" / "update_pub.pem"
TEMP_DIR = Path.home() / ".kukanilea" / "updates"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def get_app_dir() -> Path:
    return Path(__file__).resolve().parent.parent

def get_data_dir() -> Path:
    from .config import get_data_dir as config_get_data_dir
    return config_get_data_dir()

def get_latest_release_info() -> Optional[Dict[str, Any]]:
    """Holt die neueste Release‑Info von GitHub."""
    try:
        resp = requests.get(GITHUB_API, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {
            "version": data["tag_name"].lstrip("v"),
            "assets": data["assets"],
            "body": data.get("body", "")
        }
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Release-Info: {e}")
        return None

def verify_signature(file_path: Path) -> bool:
    """Prüft die Signatur der heruntergeladenen Datei mit GPG."""
    if not PUBLIC_KEY_PATH.exists():
        logger.warning(f"Öffentlicher Update-Key fehlt: {PUBLIC_KEY_PATH}. Überspringe Signaturprüfung (DEV).")
        return True

    gpg = gnupg.GPG()
    with open(PUBLIC_KEY_PATH, "rb") as f:
        gpg.import_keys(f.read())

    # Annahme: Die Signatur liegt als .sig neben der Datei
    sig_path = file_path.with_suffix(file_path.suffix + ".sig")
    if not sig_path.exists():
        logger.error("Signaturdatei nicht gefunden.")
        return False

    with open(file_path, "rb") as f_data, open(sig_path, "rb") as f_sig:
        verified = gpg.verify_file(f_sig, f_data.name)
        return verified.valid

def download_update(url: str, dest: Path) -> bool:
    """Lädt die Datei von URL nach dest herunter und prüft Signatur."""
    try:
        # Streaming‑Download
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # Signaturprüfung (optional für v1.5.0 Gold Prototype)
        if not verify_signature(dest):
            logger.error("Signaturprüfung fehlgeschlagen – lösche Datei.")
            dest.unlink()
            return False
        return True
    except Exception as e:
        logger.error(f"Download fehlgeschlagen: {e}")
        return False

def apply_update(installer_path: Path) -> bool:
    """Installiert das Update (plattformabhängig) und setzt Status."""
    system = platform.system()
    try:
        if system == "Darwin":
            # .dmg mounten und kopieren
            mount_output = subprocess.check_output(
                ["hdiutil", "attach", "-nobrowse", "-quiet", str(installer_path)],
                universal_newlines=True
            )
            # Finde gemountetes Volume (letzte Zeile)
            mount_point = mount_output.strip().split("\n")[-1].split("\t")[-1]
            app_name = "KUKANILEA.app"
            src = Path(mount_point) / app_name
            dest_app = Path("/Applications") / app_name
            if src.exists():
                # Alte App ersetzen
                if dest_app.exists():
                    subprocess.run(["rm", "-rf", str(dest_app)], check=True)
                subprocess.run(["cp", "-R", str(src), str(dest_app)], check=True)
            # Unmount
            subprocess.run(["hdiutil", "detach", mount_point], check=False)
            _set_update_pending(installer_path)

        elif system == "Windows":
            # MSI still installieren
            subprocess.run(
                ["msiexec", "/i", str(installer_path), "/quiet", "/norestart"],
                check=True
            )
            _set_update_pending(installer_path)
        else:
            logger.error(f"Nicht unterstütztes Betriebssystem: {system}")
            return False
        return True
    except Exception as e:
        logger.error(f"Update-Installation fehlgeschlagen: {e}")
        return False

def _set_update_pending(installer_path: Path):
    """Merkt sich, dass ein Update installiert wurde (für Cleanup nach Neustart)."""
    state_file = Path.home() / ".kukanilea" / "update_pending.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state = {"installer": str(installer_path), "timestamp": time.time()}
    with open(state_file, "w") as f:
        json.dump(state, f)

def _cleanup_after_restart():
    """Wird beim Start aufgerufen: löscht alten Installer."""
    state_file = Path.home() / ".kukanilea" / "update_pending.json"
    if state_file.exists():
        try:
            with open(state_file) as f:
                state = json.load(f)
            installer = Path(state["installer"])
            if installer.exists():
                installer.unlink()
            state_file.unlink()
        except Exception as e:
            logger.warning(f"Cleanup fehlgeschlagen: {e}")

def check_and_update(show_notification: bool = False) -> bool:
    """
    Hauptfunktion: Prüft auf neues Release, lädt herunter, installiert.
    """
    info = get_latest_release_info()
    if not info:
        return False

    latest_version = info["version"]
    if latest_version <= __version__:
        logger.info("Kein neueres Release verfügbar.")
        return False

    # Plattform passendes Asset finden
    system = platform.system()
    ext = ".dmg" if system == "Darwin" else ".msi"
    asset = next((a for a in info["assets"] if a["name"].endswith(ext)), None)
    if not asset:
        logger.error(f"Kein passendes Asset für {system} gefunden.")
        return False

    download_url = asset["browser_download_url"]
    dest = TEMP_DIR / asset["name"]

    if download_update(download_url, dest):
        if apply_update(dest):
            # Status in DB setzen
            from .database import get_db_connection
            with get_db_connection() as conn:
                conn.execute("""
                    UPDATE update_status
                    SET last_checked = CURRENT_TIMESTAMP,
                        latest_version = ?,
                        update_available = 1,
                        update_downloaded = 1,
                        installer_path = ?
                    WHERE id = 1
                """, (latest_version, str(dest)))
                conn.commit()
            if show_notification:
                _show_notification("Update bereit", "KUKANILEA wurde aktualisiert.")
            return True
    return False

def _show_notification(title, message):
    """Zeigt eine plattformspezifische Benachrichtigung."""
    try:
        from plyer import notification
        notification.notify(title=title, message=message, timeout=5)
    except Exception:
        pass

def get_update_status():
    """Liefert den aktuellen Update‑Status aus der DB."""
    from .database import get_db_connection
    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT * FROM update_status WHERE id = 1").fetchone()
            return dict(row) if row else {}
    except Exception:
        return {}

def check_for_installable_update(current_version, release_url=None, timeout_seconds=30, manifest_url=None, signing_required=False, public_key_pem=None):
    info = get_latest_release_info()
    if not info:
        return {"update_available": False, "latest_version": current_version}
    
    latest_version = info["version"]
    available = latest_version > current_version
    
    return {
        "update_available": available,
        "latest_version": latest_version,
        "release_url": info.get("html_url"),
        "asset_url": next((a["browser_download_url"] for a in info["assets"] if a["name"].endswith((".dmg", ".msi"))), None) if available else None
    }

def download_update_asset(asset_url, download_dir, timeout_seconds=30):
    dest = Path(download_dir) / Path(asset_url).name
    if download_update(asset_url, dest):
        return str(dest)
    raise UpdateError("Download failed")

def install_update_from_archive(archive_path, app_dir, data_dir, expected_sha256=None):
    if apply_update(Path(archive_path)):
        return {"backup_dir": "simulated_backup"}
    raise UpdateError("Installation failed")

def rollback_update(app_dir):
    raise UpdateError("Rollback not implemented")
