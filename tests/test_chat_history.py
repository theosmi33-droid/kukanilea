from app.db import AuthDB


def test_chat_history_persistence(tmp_path):
    db = AuthDB(tmp_path / "auth.db")
    db.init()
    db.add_chat_message(
        ts="2024-01-01T00:00:00",
        tenant_id="KUKANILEA",
        username="dev",
        role="ADMIN",
        direction="user",
        message="hallo",
    )
    rows = db.list_chat_messages(tenant_id="KUKANILEA", limit=5)
    assert rows
    assert rows[0]["message"] == "hallo"
