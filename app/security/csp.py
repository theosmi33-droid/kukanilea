from __future__ import annotations


def build_csp_header() -> str:
    # Keep a strict baseline while preserving legacy inline template compatibility.
    # Unsafe inline remains only where migration to nonced/static assets is pending.
    # No remote origins and no blob/eval allowances are permitted.
    directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",
        "script-src 'self' 'unsafe-inline'",
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
