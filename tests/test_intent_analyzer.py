from app.ai.intent_analyzer import detect_write_intent, semantic_guard


def test_detect_write_intent_matches_write_verbs():
    assert detect_write_intent("Bitte sende das jetzt") is True
    assert detect_write_intent("create a task") is True
    assert detect_write_intent("zeige mir den status") is False


def test_detect_write_intent_uses_semantic_guard(monkeypatch):
    monkeypatch.setattr(semantic_guard, "is_write_like", lambda _text: (True, "llm"))
    assert detect_write_intent("mach das bitte") is True


def test_detect_write_intent_covers_required_write_verbs():
    for verb in ("create", "delete", "send", "update", "upload", "remove"):
        assert detect_write_intent(f"please {verb} this") is True
