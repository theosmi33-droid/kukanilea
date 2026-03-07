from __future__ import annotations


def build_csp_header(script_nonce: str | None = None) -> str:
    # Enterprise baseline: block remote origins, object embedding and mixed content.
    # Inline scripts are only allowed via per-request nonces.
    nonce_value = (script_nonce or "").strip()
    script_sources = "'self'"
    if nonce_value:
        script_sources = f"{script_sources} 'nonce-{nonce_value}'"

    directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",
        f"script-src {script_sources}",
        f"script-src-elem {script_sources}",
        "script-src-attr 'none'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        "media-src 'self'",
        "connect-src 'self'",
        "worker-src 'self'",
        "manifest-src 'self'",
        "frame-src 'none'",
        "object-src 'none'",
        "block-all-mixed-content",
        "upgrade-insecure-requests",
    ]
    return "; ".join(directives) + ";"
