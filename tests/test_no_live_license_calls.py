from __future__ import annotations

import os


def test_no_live_license_calls_in_ci() -> None:
    ci = str(os.environ.get("CI", "")).strip().lower()
    if ci not in {"1", "true", "yes"}:
        return

    candidate_urls = [
        str(os.environ.get("LICENSE_SERVER_URL", "")).strip().lower(),
        str(os.environ.get("KUKANILEA_LICENSE_VALIDATE_URL", "")).strip().lower(),
    ]
    for url in candidate_urls:
        if not url:
            continue
        assert ("127.0.0.1" in url) or (
            "localhost" in url
        ), "LICENSE validation in CI must use a local stub URL"
