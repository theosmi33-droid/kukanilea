from app.security.csp import build_csp_header


def test_csp_contains_only_required_exceptions():
    csp = build_csp_header()
    assert "default-src 'self'" in csp
    assert "script-src 'self' 'unsafe-inline'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "object-src 'none'" in csp
    assert "frame-src 'none'" in csp
    assert "worker-src 'self'" in csp
    assert "media-src 'self'" in csp
    assert "blob:" not in csp
    assert "eval(" not in csp
    assert "data:" not in csp.split("connect-src", 1)[1]
