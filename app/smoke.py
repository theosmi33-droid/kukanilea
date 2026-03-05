from __future__ import annotations

import os
import re
import tempfile
import time

from app import create_app
from app.auth import hash_password
from app.db import AuthDB


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_dir = os.path.abspath(tmp)
        os.environ["HOME"] = tmp_dir
        os.environ["KUKANILEA_AUTH_DB"] = os.path.join(tmp_dir, "auth.db")
        os.environ["DB_FILENAME"] = os.path.join(tmp_dir, "core.db")
        os.environ["BASE_DIRNAME"] = "Kukanilea_Smoke"

        app = create_app()
        with app.app_context():
            routes = [rule.rule for rule in app.url_map.iter_rules()]
            if "/login" not in routes:
                raise SystemExit("/login route missing")

            auth_db: AuthDB = app.extensions["auth_db"]
            now = "2024-01-01T00:00:00"
            auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
            auth_db.upsert_user("dev", hash_password("dev"), now)
            auth_db.upsert_membership("dev", "KUKANILEA", "DEV", now)

        client = app.test_client()

        health = client.get("/api/health")
        if health.status_code != 200:
            raise SystemExit("health failed")

        login_page = client.get("/login")
        if login_page.status_code != 200:
            raise SystemExit("login page failed")
        login_html = login_page.get_data(as_text=True)
        with client.session_transaction() as sess:
            csrf_token = str(sess.get("csrf_token", "") or "")
            if not csrf_token:
                token_match = re.search(r'name="csrf-token"\s+content="([^"]+)"', login_html)
                if not token_match:
                    token_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_html)
                csrf_token = token_match.group(1) if token_match else ""
            sess["user"] = "dev"
            sess["role"] = "DEV"
            sess["tenant_id"] = "KUKANILEA"
            sess["csrf_token"] = csrf_token or "smoke-csrf-token"
            csrf_token = sess["csrf_token"]

        start = time.time()
        chat = client.post(
            "/api/chat",
            json={"q": "rechnung", "safe_mode": True},
            headers={"X-CSRF-Token": csrf_token},
        )
        latency_ms = int((time.time() - start) * 1000)
        if chat.status_code != 200:
            raise SystemExit("chat failed")

        search = client.post(
            "/api/search",
            json={"query": "rechnung"},
            headers={"X-CSRF-Token": csrf_token},
        )
        if search.status_code != 200:
            raise SystemExit("search failed")

        import io

        data = {"file": (io.BytesIO(b"demo"), "demo.txt")}
        upload = client.post("/upload", data=data, headers={"X-CSRF-Token": csrf_token})
        if upload.status_code != 200:
            raise SystemExit("upload failed")

        if latency_ms > 2000:
            raise SystemExit("chat latency too high")

    print("smoke ok")


if __name__ == "__main__":
    main()
