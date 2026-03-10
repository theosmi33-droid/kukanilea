from pathlib import Path


def test_haptic_css_does_not_contain_local_filesystem_paths() -> None:
    runtime_css = Path("app/static/css/haptic.css").read_text(encoding="utf-8")
    source_css = Path("static/css/haptic.css").read_text(encoding="utf-8")

    for content in (runtime_css, source_css):
        assert "@Library/" not in content
        assert "/Users/" not in content
        assert "@keyframes skeleton-loading" in content
