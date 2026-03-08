from pathlib import Path


def test_upload_progress_polling_is_visibility_aware_with_backoff() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "const VISIBLE_POLL_INTERVAL_MS = 1000;" in html
    assert "const HIDDEN_POLL_INTERVAL_MS = 5000;" in html
    assert "const ERROR_BACKOFF_BASE_MS = 2000;" in html
    assert "const ERROR_BACKOFF_MAX_MS = 30000;" in html
    assert 'document.addEventListener("visibilitychange"' in html
    assert "scheduleProgressPollAfterError" in html
    assert "progressPollRetryCount = 0;" in html
