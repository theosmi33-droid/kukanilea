from pathlib import Path


def _visualizer_source() -> str:
    path = Path(__file__).resolve().parents[2] / "app" / "routes" / "visualizer.py"
    return path.read_text(encoding="utf-8")


def test_visualizer_tenant_roots_include_pending_done_dirs():
    source = _visualizer_source()
    assert "PENDING_DIR = _core_get(\"PENDING_DIR\")" in source
    assert "DONE_DIR = _core_get(\"DONE_DIR\")" in source


def test_visualizer_tenant_scope_uses_all_configured_roots():
    source = _visualizer_source()
    assert "(BASE_PATH, EINGANG, PENDING_DIR, DONE_DIR)" in source
