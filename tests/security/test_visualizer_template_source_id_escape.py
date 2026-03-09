from pathlib import Path


def _template_text() -> str:
    template = Path(__file__).resolve().parents[2] / "app" / "templates" / "visualizer.html"
    return template.read_text(encoding="utf-8")


def test_visualizer_source_id_uses_escaped_binding():
    text = _template_text()
    assert 'data-id="${esc(it.id)}"' in text


def test_visualizer_source_id_does_not_use_raw_binding():
    text = _template_text()
    assert 'data-id="${it.id}"' not in text
