import multiprocessing
import os

# Add project root to path
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

sys.path.append(str(Path(__file__).parent.parent.parent))

# DO NOT IMPORT app AT TOP LEVEL


def run_server(port, auth_db_path, core_db_path, user_data_root):
    """Worker function to run the Flask app."""
    # SET ENV FIRST
    os.environ["KUKANILEA_AUTH_DB"] = str(auth_db_path)
    os.environ["KUKANILEA_CORE_DB"] = str(core_db_path)
    os.environ["KUKANILEA_USER_DATA_ROOT"] = str(user_data_root)

    # NOW imports
    from app import create_app
    from app.auth import hash_password
    from app.db import AuthDB

    adb = AuthDB(Path(auth_db_path))
    adb.init()
    now = "2024-01-01T00:00:00"
    hpw = hash_password("admin")
    adb.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    adb.upsert_user("admin", hpw, now)
    adb.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    # Bypass first-run check by creating a license file
    lic_path = Path(user_data_root) / "license.json"
    lic_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    lic_path.write_text(json.dumps({"valid": True, "plan": "ENTERPRISE"}))

    app = create_app()
    app.run(port=port, debug=False, use_reloader=False)


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """Starts the KUKANILEA server for E2E testing."""

    tmp_dir = tmp_path_factory.mktemp("e2e_data")
    auth_db_path = tmp_dir / "auth.db"
    core_db_path = tmp_dir / "core.db"
    port = 5052

    p = multiprocessing.Process(
        target=run_server,
        args=(port, str(auth_db_path), str(core_db_path), str(tmp_dir)),
    )
    p.start()

    # Wait for server to be ready
    time.sleep(3)
    yield f"http://127.0.0.1:{port}"

    p.terminate()
    p.join()


def test_full_workflow(page: Page, server: str):
    """
    Tests the full UI workflow:
    Login -> Upload -> OCR Transition -> Review
    """
    # 1. Login
    page.goto(f"{server}/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.click('button[type="submit"]')

    # Verify we are on the dashboard
    expect(page).to_have_url(f"{server}/")
    expect(page.locator("text=Beleg-Zentrale")).to_be_visible()

    # 2. Upload
    # Create a dummy file
    test_file = Path("test_e2e_document.txt")
    test_file.write_text("KDNR: 12345\nRechnung vom 01.01.2026\nBetrag: 100 EUR")

    page.set_input_files('input[name="file"]', str(test_file))
    page.click('button:has-text("Analyse starten")')

    # 3. Wait for OCR and Transition
    # The UI should show progress and then redirect to /review/<token>/kdnr
    # We wait for the URL to change to something containing "/review/"
    page.wait_for_url("**/review/**/kdnr", timeout=15000)

    expect(page.get_by_text("Review", exact=True)).to_be_visible()

    # Cleanup
    test_file.unlink()


def test_unauthorized_access(page: Page, server: str):
    """Verifies that unauthorized access redirects to login."""
    page.goto(f"{server}/admin/mesh")
    # Should redirect to login because no session
    expect(page).to_have_url(re_compile(rf"{server}/login\?next=.*"))


def re_compile(pattern):
    import re

    return re.compile(pattern)
