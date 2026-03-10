from __future__ import annotations

from pathlib import Path


TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "app" / "templates" / "review.html"


def _template_text() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def test_review_badges_use_data_attributes_for_kdnr_and_name() -> None:
    text = _template_text()

    assert "data-value=\"{{k}}\"" in text
    assert "data-value=\"{{n}}\"" in text
    assert "document.getElementById('kdnr_input').value=this.dataset.value" in text
    assert "document.getElementById('name_input').value=this.dataset.value" in text


def test_review_badges_do_not_embed_raw_suggestions_in_onclick_literals() -> None:
    text = _template_text()

    assert "document.getElementById('kdnr_input').value='{{k}}'" not in text
    assert "document.getElementById('name_input').value='{{n}}'" not in text
    assert "+ '{{kw}}'" not in text


def test_keyword_badges_append_from_dataset_value() -> None:
    text = _template_text()

    assert "data-value=\"{{kw}}\"" in text
    assert "+ this.dataset.value;" in text
