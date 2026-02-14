from __future__ import annotations

from pathlib import Path


def test_templates_do_not_use_safe_filter() -> None:
    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    assert templates_dir.exists()

    hits: list[str] = []
    for tpl in sorted(templates_dir.rglob("*.html")):
        content = tpl.read_text(encoding="utf-8")
        if "|safe" in content:
            hits.append(str(tpl.relative_to(templates_dir.parent)))

    assert not hits, "unsafe '|safe' usage found in templates:\n" + "\n".join(hits)
