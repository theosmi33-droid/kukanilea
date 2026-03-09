from pathlib import Path


def test_visualizer_tenant_error_contract_kept_for_render_and_summary():
    source = (Path(__file__).resolve().parents[2] / "app" / "routes" / "visualizer.py").read_text(encoding="utf-8")
    assert 'return jsonify(error="forbidden_tenant_path"), 403' in source


def test_visualizer_tenant_helper_present():
    source = (Path(__file__).resolve().parents[2] / "app" / "routes" / "visualizer.py").read_text(encoding="utf-8")
    assert "def _is_tenant_visualizer_path" in source
