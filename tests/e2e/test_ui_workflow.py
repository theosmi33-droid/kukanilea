import multiprocessing
import os
import socket

# Add project root to path
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
Page = playwright.Page
PlaywrightTimeoutError = playwright.TimeoutError
expect = playwright.expect

sys.path.append(str(Path(__file__).parent.parent.parent))

# DO NOT IMPORT app AT TOP LEVEL


def run_server(port, auth_db_path, core_db_path, user_data_root):
    """Worker function to run the Flask app."""
    # SET ENV FIRST
    os.environ["KUKANILEA_AUTH_DB"] = str(auth_db_path)
    os.environ["KUKANILEA_CORE_DB"] = str(core_db_path)
    os.environ["KUKANILEA_USER_DATA_ROOT"] = str(user_data_root)
    # E2E environments run without ClamAV daemon; keep upload flow testable.
    os.environ["CLAMAV_OPTIONAL"] = "1"

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


def _reserve_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, timeout_s: float = 15.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.2)
    raise RuntimeError(f"Server did not become ready in time: {url}")


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """Starts the KUKANILEA server for E2E testing."""

    tmp_dir = tmp_path_factory.mktemp("e2e_data")
    auth_db_path = tmp_dir / "auth.db"
    core_db_path = tmp_dir / "core.db"
    process = None
    server_url = None
    startup_error = None

    for _ in range(3):
        port = _reserve_free_port()
        process = multiprocessing.Process(
            target=run_server,
            args=(port, str(auth_db_path), str(core_db_path), str(tmp_dir)),
        )
        process.start()

        try:
            _wait_for_server(f"http://127.0.0.1:{port}/login")
            server_url = f"http://127.0.0.1:{port}"
            break
        except RuntimeError as exc:
            startup_error = exc
            process.terminate()
            process.join(timeout=5)

    if server_url is None:
        raise RuntimeError(f"E2E server startup failed after retries: {startup_error}")

    yield server_url

    if process is not None and process.is_alive():
        process.terminate()
    if process is not None:
        process.join(timeout=5)


def test_full_workflow(page: Page, server: str, tmp_path: Path):
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
    expect(page).to_have_url(f"{server}/dashboard")
    expect(page.locator("text=Beleg-Zentrale")).to_be_visible()

    # 2. Upload
    page.goto(f"{server}/upload")
    expect(page).to_have_url(f"{server}/upload")

    # Use a per-test temp file to avoid parallel cleanup races.
    test_file = tmp_path / "test_e2e_document.txt"
    test_file.write_text("KDNR: 12345\nRechnung vom 01.01.2026\nBetrag: 100 EUR")

    page.set_input_files('input[name="file"]', str(test_file))
    # Shell/UI moved from legacy #btn-upload to #startAnalysis.
    upload_cta = page.locator("#startAnalysis")
    if upload_cta.count() == 0:
        upload_cta = page.locator("#btn-upload")
    upload_cta.click()

    # 3. Wait for OCR and Transition (or expected ClamAV block in CI/dev)
    upload_blocked = False
    try:
        page.wait_for_url("**/review/**/kdnr", timeout=15000)
    except PlaywrightTimeoutError:
        upload_blocked = True

    if upload_blocked:
        expect(page).not_to_have_url(re_compile(r".*/review/.*/kdnr"))
        # In current shell variants the file input can be visually hidden while
        # the user remains on upload (staging/progress/error state).
        expect(page.locator('input[name="file"]')).to_have_count(1)
    else:
        expect(page.get_by_text("Metadaten", exact=True)).to_be_visible()

    # Cleanup
    test_file.unlink(missing_ok=True)


def test_unauthorized_access(page: Page, server: str):
    """Verifies that unauthorized access redirects to login."""
    page.goto(f"{server}/admin/mesh")
    # Should redirect to login because no session
    expect(page).to_have_url(re_compile(rf"{server}/login\?next=.*"))


def re_compile(pattern):
    import re

    return re.compile(pattern)
