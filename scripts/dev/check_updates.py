#!/usr/bin/env python3
"""
scripts/dev/check_updates.py
KUKANILEA CORE-DEPENDENCY ADVISOR
Checks PyPI for safer/newer versions of core libraries.
Focus: ollama, Flask, SQLAlchemy.
"""

import logging
from pathlib import Path

import requests
from packaging import version

# Logger-Setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("kukanilea.updates")

CORE_LIBS = ["ollama", "Flask", "SQLAlchemy"]
REQUIREMENTS_FILE = Path(__file__).parent.parent.parent / "requirements.txt"


def get_current_version(lib_name):
    """Parses requirements.txt to find the current pinned version."""
    if not REQUIREMENTS_FILE.exists():
        return None

    with open(REQUIREMENTS_FILE, "r") as f:
        for line in f:
            if line.lower().startswith(lib_name.lower() + "=="):
                return line.split("==")[1].strip()
    return None


def get_latest_version(lib_name):
    """Queries PyPI API for the latest version of a package."""
    try:
        url = f"https://pypi.org/pypi/{lib_name}/json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data["info"]["version"]
    except Exception as e:
        logger.error(f"Failed to fetch {lib_name} info from PyPI: {e}")
        return None


def check_updates():
    """Checks for updates for all core libraries."""
    logger.info("Checking for core library updates on PyPI...")
    updates_found = False

    for lib in CORE_LIBS:
        current = get_current_version(lib)
        latest = get_latest_version(lib)

        if not current:
            logger.warning(f"{lib} is not pinned in requirements.txt or not found.")
            continue

        if not latest:
            continue

        if version.parse(latest) > version.parse(current):
            logger.info(f"✨ Update available for {lib}: {current} -> {latest}")
            updates_found = True
        else:
            logger.info(f"✅ {lib} is up to date ({current}).")

    if not updates_found:
        logger.info("All core libraries are currently at their latest pinned versions.")


if __name__ == "__main__":
    check_updates()
