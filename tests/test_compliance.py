import pytest
import time
import logging
from app.session import create_session, validate_session, invalidate_session, SESSION_IDLE_TIMEOUT
from app.logging_utils import PIISafeFormatter
from fastapi import HTTPException

def test_session_lifecycle():
    """Verify session creation, validation and manual invalidation."""
    sid = create_session("user1", "tenantA", "ADMIN")
    assert validate_session(sid)["user_id"] == "user1"
    
    invalidate_session(sid)
    with pytest.raises(HTTPException) as exc:
        validate_session(sid)
    assert exc.value.status_code == 401

def test_session_idle_timeout():
    """Verify that sessions expire after the idle timeout."""
    sid = create_session("user2", "tenantB", "USER")
    
    # Mock last activity to be older than timeout
    from app.session import sessions
    sessions[sid]["last_activity"] = time.time() - (SESSION_IDLE_TIMEOUT + 1)
    
    with pytest.raises(HTTPException) as exc:
        validate_session(sid)
    assert "timed out" in exc.value.detail

def test_pii_log_redaction():
    """Verify that PII (Email/Phone) is redacted from logs."""
    formatter = PIISafeFormatter()
    record = logging.LogRecord("test", logging.INFO, "path", 10, "Contact user@example.com at +4912345678", None, None)
    formatted = formatter.format(record)
    
    assert "user@example.com" not in formatted
    assert "+4912345678" not in formatted
    assert "[REDACTED_PII]" in formatted
