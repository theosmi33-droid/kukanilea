from __future__ import annotations


def build_csp_header() -> str:
    # Keep a strict baseline; allow inline styles for legacy templates only.
    directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "media-src 'self' data: blob:",
        "connect-src 'self'",
        "worker-src 'self' blob:",
        "manifest-src 'self'",
        "frame-src 'self' blob:",
        "object-src 'none'",
        "block-all-mixed-content",
        "upgrade-insecure-requests",
    ]
    return "; ".join(directives) + ";"
