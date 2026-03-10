from pathlib import Path


def test_toast_renderer_does_not_use_innerhtml_for_message() -> None:
    script = Path("app/static/js/ui-feedback.js").read_text(encoding="utf-8")

    assert "toast.innerHTML" not in script
    assert "messageEl.textContent" in script
