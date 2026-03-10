from pathlib import Path


def test_haptic_css_does_not_contain_local_filesystem_paths() -> None:
    runtime_css = Path("app/static/css/haptic.css").read_text(encoding="utf-8")
    contents = [runtime_css]
    source_css_path = Path("static/css/haptic.css")
    if source_css_path.exists():
        contents.append(source_css_path.read_text(encoding="utf-8"))

    for content in contents:
        assert "@Library/" not in content
        assert "/Users/" not in content
        assert "@keyframes skeleton-loading" in content
