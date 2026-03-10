#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

CDN_PATTERNS = re.compile(
    r"(https?://|//)(cdn|unpkg|cdnjs|jsdelivr)",
    re.IGNORECASE,
)
EXTERNAL_ASSET_PATTERNS = re.compile(
    r"\b(?:src|href|poster|srcset|action|formaction)\s*=\s*(?:[\"'])?(?:https?:)?//",
    re.IGNORECASE,
)
INLINE_HANDLER_PATTERN = re.compile(
    r"(?:^|[\s<])on[a-z]+\s*=",
    re.IGNORECASE,
)
JAVASCRIPT_PATH_PATTERN = re.compile(
    r"j\s*a\s*v\s*a\s*s\s*c\s*r\s*i\s*p\s*t\s*:",
    re.IGNORECASE,
)
TEXT_EXTENSIONS = {".py", ".html", ".js", ".css", ".txt", ".md", ".json", ".yaml", ".yml"}
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore\s+(?:all\s+|previous\s+)?instructions?\b"),
    re.compile(r"(?i)\bdisregard\s+(?:all\s+|previous\s+)?instructions?\b"),
    re.compile(r"(?i)\boverride\s+(?:system\s+prompt|instructions?|polic(?:y|ies)|guardrails?)\b"),
    re.compile(r"(?i)\b(?:reveal|show)\s+(?:the\s+)?(?:system\s+prompt|hidden\s+instructions?)\b"),
    re.compile(r"(?i)\b(?:bypass|disable)\s+(?:all\s+)?(?:security|guardrails?|safety)\b"),
]
PROMPT_SCAN_ALLOWLIST = {
    "app/ai/guardrails.py",
    "app/security/gates.py",
    "app/security/untrusted_input.py",
    "app/agents/guards.py",
    "app/agents/input_validator.py",
    "kukanilea/guards.py",
    "kukanilea/orchestrator/manager_agent.py",
}


def check_cdn_urls(paths: list[str] | None = None) -> list[str]:
    roots = [Path(p) for p in (paths or ["app/templates", "app/static/sim"])]
    errors: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for full_path in root.rglob("*"):
            if not full_path.is_file() or full_path.suffix not in {".html", ".js", ".css"}:
                continue
            with full_path.open("r", encoding="utf-8") as fh:
                for line_num, line in enumerate(fh, 1):
                    if CDN_PATTERNS.search(line):
                        if 'xmlns="http://www.w3.org/2000/svg"' in line:
                            continue
                        errors.append(f"CDN URL found in {full_path}:{line_num}: {line.strip()}")
    return errors


def check_external_asset_urls(paths: list[str] | None = None) -> list[str]:
    class _ExternalAssetHTMLParser(HTMLParser):
        def __init__(self, full_path: Path, errors: list[str]) -> None:
            super().__init__(convert_charrefs=False)
            self.full_path = full_path
            self.errors = errors

        def _check_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attrs_dict = {name.lower(): value for name, value in attrs}
            if tag.lower() == "svg" and attrs_dict.get("xmlns") == "http://www.w3.org/2000/svg":
                return

            for attr_name, attr_value in attrs:
                if attr_name.lower() not in {"src", "href", "poster", "srcset", "action", "formaction"}:
                    continue
                if attr_value is None:
                    continue
                if re.match(r"^(?:https?:)?//", attr_value, re.IGNORECASE):
                    line_num, _ = self.getpos()
                    tag_preview = (self.get_starttag_text() or f"<{tag}>").splitlines()[0].strip()
                    self.errors.append(
                        f"External asset URL found in {self.full_path}:{line_num}: {tag_preview}"
                    )
                    return

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            self._check_tag(tag, attrs)

        def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            self._check_tag(tag, attrs)

    roots = [Path(p) for p in (paths or ["app/templates"])]
    errors: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for full_path in root.rglob("*.html"):
            content = full_path.read_text(encoding="utf-8")
            parser = _ExternalAssetHTMLParser(full_path, errors)
            parser.feed(content)
    return errors


def check_shell_template_inline_handlers(path: str = "app/templates/layout.html") -> list[str]:
    template = Path(path)
    errors: list[str] = []
    if not template.exists():
        return errors

    content = template.read_text(encoding="utf-8")
    for line_num, line in enumerate(content.splitlines(), 1):
        if INLINE_HANDLER_PATTERN.search(line):
            errors.append(f"Inline event handler found in shell template {template}:{line_num}: {line.strip()}")
        if JAVASCRIPT_PATH_PATTERN.search(line):
            errors.append(f"javascript: URL found in shell template {template}:{line_num}: {line.strip()}")
        if "rel=\"preload\"" in line and "onload=" in line:
            errors.append(f"CSP-unsafe preload onload hack in {template}:{line_num}: {line.strip()}")
    return errors


def check_htmx_confirm(path: str = "app/templates") -> list[str]:
    hx_methods = ["hx-post", "hx-put", "hx-patch", "hx-delete"]
    root = Path(path)
    errors: list[str] = []
    if not root.exists():
        return errors

    for full_path in root.rglob("*.html"):
        content = full_path.read_text(encoding="utf-8")
        tags = re.finditer(r"(<[^>]+>)", content, re.DOTALL)
        for match in tags:
            tag = match.group(0)
            has_method = any(f"{method}=" in tag for method in hx_methods)
            has_confirm = "hx-confirm=" in tag
            if has_method and not has_confirm:
                line_num = content.count("\n", 0, match.start()) + 1
                tag_preview = tag.splitlines()[0] if "\n" in tag else tag
                errors.append(
                    f"HTMX method without hx-confirm in {full_path}:{line_num}: {tag_preview}"
                )
    return errors


def check_htmx_csrf(path: str = "app/templates") -> list[str]:
    hx_methods = ["hx-post", "hx-put", "hx-patch", "hx-delete"]
    root = Path(path)
    errors: list[str] = []
    if not root.exists():
        return errors

    for full_path in root.rglob("*.html"):
        content = full_path.read_text(encoding="utf-8")
        tags = list(re.finditer(r"(<[^>]+>)", content, re.DOTALL))
        for idx, match in enumerate(tags):
            tag = match.group(0)
            has_method = any(f"{method}=" in tag for method in hx_methods)
            if not has_method:
                continue

            has_csrf_header = "hx-headers" in tag and "X-CSRF-Token" in tag
            if tag.lower().startswith("<form"):
                closing_tag = re.search(r"</form>", content[match.end():], re.IGNORECASE)
                form_end = match.end() + closing_tag.start() if closing_tag else len(content)
                form_body = content[match.end():form_end]
                has_hidden_csrf = 'name="csrf_token"' in form_body or "name='csrf_token'" in form_body
                has_csrf = has_csrf_header or has_hidden_csrf
            else:
                has_csrf = has_csrf_header

            if not has_csrf:
                line_num = content.count("\n", 0, match.start()) + 1
                tag_preview = tag.splitlines()[0] if "\n" in tag else tag
                errors.append(
                    f"HTMX mutation without CSRF token/header in {full_path}:{line_num}: {tag_preview}"
                )
    return errors


def _is_allowlisted(path: Path, allowlist: set[str]) -> bool:
    normalized = path.as_posix()
    return any(normalized == entry or normalized.endswith(f"/{entry}") for entry in allowlist)


def check_prompt_injection_surface(paths: list[str] | None = None) -> list[str]:
    scan_roots = [Path(p) for p in (paths or ["app", "kukanilea"])]
    errors: list[str] = []
    for root in scan_roots:
        if not root.exists():
            continue
        for full_path in root.rglob("*"):
            if not full_path.is_file() or full_path.suffix not in TEXT_EXTENSIONS:
                continue
            if _is_allowlisted(full_path, PROMPT_SCAN_ALLOWLIST):
                continue
            try:
                with full_path.open("r", encoding="utf-8") as fh:
                    for line_num, line in enumerate(fh, 1):
                        if any(pattern.search(line) for pattern in PROMPT_INJECTION_PATTERNS):
                            errors.append(
                                "Prompt-injection control phrase found outside allowlist in "
                                f"{full_path}:{line_num}: {line.strip()}"
                            )
            except UnicodeDecodeError:
                continue
    return errors


if __name__ == "__main__":
    print("[GUARDRAIL] Verifying CDN, external assets, shell inline handlers, HTMX confirm/CSRF, and prompt-injection surface...")
    cdn_errors = check_cdn_urls()
    external_asset_errors = check_external_asset_urls()
    shell_inline_errors = check_shell_template_inline_handlers()
    htmx_errors = check_htmx_confirm()
    htmx_csrf_errors = check_htmx_csrf()
    injection_errors = check_prompt_injection_surface()

    all_errors = cdn_errors + external_asset_errors + shell_inline_errors + htmx_errors + htmx_csrf_errors + injection_errors
    if all_errors:
        for err in all_errors:
            print(f"FAILED: {err}")
        sys.exit(1)

    print("OK: All guardrail checks passed.")
    sys.exit(0)
