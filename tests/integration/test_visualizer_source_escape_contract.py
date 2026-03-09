from pathlib import Path


def test_visualizer_template_keeps_esc_helper_for_attributes():
    template = Path(__file__).resolve().parents[2] / "app" / "templates" / "visualizer.html"
    text = template.read_text(encoding="utf-8")
    assert "const esc =" in text
    assert "replace(/&/g" in text
    assert 'replace(/\\"/g' in text


def test_visualizer_list_markup_escapes_name_and_source():
    template = Path(__file__).resolve().parents[2] / "app" / "templates" / "visualizer.html"
    text = template.read_text(encoding="utf-8")
    assert '${esc(it.name || "(ohne Name)")}' in text
    assert '${esc(it.source || "vault")}' in text
