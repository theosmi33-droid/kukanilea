#!/usr/bin/env python3
"""
KUKANILEA - Predictive Fleet Telemetry (Opt-In)
Sammlung von anonymisierten Hardware-Health-Daten für Predictive Maintenance.
"""
import os
import sys
import json
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TELEMETRY_CONFIG = BASE_DIR / "instance" / "telemetry.json"
TELEMETRY_ENDPOINT = os.environ.get("TELEMETRY_ENDPOINT", "https://partner.kukanilea.com/api/telemetry")

def get_instance_uuid() -> str:
    """Gets or creates an anonymous instance UUID."""
    if not TELEMETRY_CONFIG.exists():
        TELEMETRY_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        config = {"uuid": str(uuid.uuid4()), "opt_in": False}
        with open(TELEMETRY_CONFIG, "w") as f:
            json.dump(config, f)
        return config["uuid"]
    
    with open(TELEMETRY_CONFIG, "r") as f:
        config = json.load(f)
        return config.get("uuid", "unknown")

def is_opt_in() -> bool:
    """Checks if the user has opted-in to telemetry."""
    if not TELEMETRY_CONFIG.exists():
        return False
    with open(TELEMETRY_CONFIG, "r") as f:
        config = json.load(f)
        return config.get("opt_in", False)

def get_disk_usage() -> float:
    """Returns disk usage percentage for the data partition."""
    try:
        data_dir = BASE_DIR / "instance"
        data_dir.mkdir(parents=True, exist_ok=True)
        st = os.statvfs(str(data_dir))
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        return round((used / total) * 100, 2)
    except Exception:
        return 0.0

def collect_telemetry() -> dict:
    """Collects ONLY hardware-health, NO customer data."""
    return {
        "uuid": get_instance_uuid(),
        "disk_space_percent": get_disk_usage(),
        "uptime_seconds": time.clock_gettime(time.CLOCK_BOOTTIME) if hasattr(time, 'CLOCK_BOOTTIME') else 0,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

def send_telemetry():
    """Sends telemetry data to the partner dashboard."""
    if not is_opt_in():
        print("Telemetry is OPT-OUT. Skipping.")
        return

    data = collect_telemetry()
    payload = json.dumps(data).encode("utf-8")
    
    req = urllib.request.Request(
        TELEMETRY_ENDPOINT, 
        data=payload, 
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in (200, 201):
                print(f"Telemetry sent successfully. Disk: {data['disk_space_percent']}%")
    except urllib.error.URLError as e:
        print(f"Failed to send telemetry: {e}")

if __name__ == "__main__":
    send_telemetry()
