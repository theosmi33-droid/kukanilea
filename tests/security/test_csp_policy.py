from flask import Response

from app.security.csp import build_csp_header


def test_csp_contains_nonce_based_script_policy():
    csp = build_csp_header("nonce-token")
    assert "default-src 'self'" in csp
    assert "script-src 'self' 'nonce-nonce-token'" in csp
    assert "script-src-elem 'self' 'nonce-nonce-token'" in csp
    assert "script-src-attr 'none'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "object-src 'none'" in csp
    assert "frame-src 'none'" in csp
    assert "worker-src 'self'" in csp
    assert "media-src 'self'" in csp
    assert "blob:" not in csp
    assert "unsafe-eval" not in csp


def test_csp_without_nonce_has_no_unsafe_inline_script_fallback():
    csp = build_csp_header()
    assert "script-src 'self'" in csp
    assert "script-src-elem 'self'" in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp
    assert "script-src-attr 'none'" in csp


def test_html_responses_are_not_rewritten_to_auto_nonce_script_tags(admin_client):
    app, client = admin_client

    @app.get("/__csp_nonce_rewrite_probe")
    def _probe() -> Response:
        return Response('<html><body><script>alert("x")</script></body></html>', mimetype="text/html")

    response = client.get("/__csp_nonce_rewrite_probe")

    body = response.get_data(as_text=True)
    assert '<script>alert("x")</script>' in body
    assert "nonce=" not in body
