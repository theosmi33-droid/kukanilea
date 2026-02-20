from __future__ import annotations

from pathlib import Path

BAD_TOKENS = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
)


def test_self_hosted_font_assets_exist() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert (repo_root / "static/css/fonts.css").exists()
    assert (repo_root / "static/fonts/inter/InterVariable.woff2").exists()
    assert (repo_root / "static/fonts/inter/InterVariable-Italic.woff2").exists()


def test_no_external_font_references_in_runtime_assets() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    roots = [repo_root / "app", repo_root / "templates", repo_root / "static"]
    suffixes = {".py", ".html", ".css", ".js"}

    offenders: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for file_path in root.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in suffixes:
                continue
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if any(token in content for token in BAD_TOKENS):
                offenders.append(file_path)

    assert not offenders, f"External font references found: {offenders}"
