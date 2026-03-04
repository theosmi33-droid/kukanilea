from __future__ import annotations


def build_csp_header() -> str:
    # Keep a strict baseline; allow inline styles/scripts for legacy templates only.
    directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "script-src 'self' 'unsafe-inline'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "frame-src 'self' blob:",
        "object-src 'none'",
    ]
    return "; ".join(directives) + ";"
