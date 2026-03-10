from __future__ import annotations

from flask import Response, jsonify


def test_does_not_auto_inject_nonce_into_script_tags(admin_client):
    app, client = admin_client

    @app.route("/__test/csp/mixed")
    def _mixed_html() -> str:
        return (
            "<html><body>"
            "<script>window.a=1;</script>"
            "<script nonce='kept'>window.b=2;</script>"
            "<script type='module'>window.c=3;</script>"
            "</body></html>"
        )

    response = client.get("/__test/csp/mixed")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert body.count("nonce=") == 1
    assert "nonce='kept'" in body


def test_does_not_mutate_non_html_responses(admin_client):
    app, client = admin_client

    @app.route("/__test/csp/json")
    def _json():
        return jsonify({"ok": True, "script": "<script>alert(1)</script>"})

    response = client.get("/__test/csp/json")
    assert response.status_code == 200
    assert response.is_json
    assert response.get_json()["script"] == "<script>alert(1)</script>"


def test_skips_streaming_html_responses(admin_client):
    app, client = admin_client

    @app.route("/__test/csp/stream")
    def _stream():
        def _generate():
            yield "<script>streamed()</script>"

        return Response(_generate(), content_type="text/html; charset=utf-8")

    response = client.get("/__test/csp/stream")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "nonce=" not in body


def test_handles_bytes_html_without_decoding_failures(admin_client):
    app, client = admin_client

    @app.route("/__test/csp/bytes")
    def _bytes_html():
        payload = b"\xff\xfe<script>bytes()</script>"
        return Response(payload, content_type="text/html")

    response = client.get("/__test/csp/bytes")
    body = response.get_data()

    assert response.status_code == 200
    assert body.startswith(b"\xff\xfe")
    assert b"<script nonce=\"" not in body
