from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = (ROOT / "app", ROOT / "kukanilea")
SKIP_DIR_NAMES = {
    "__pycache__",
    ".venv",
    ".build_venv",
    "archive",
    "reports",
    "instance",
}
EVENTLOG_FORBIDDEN_KEYS = {
    "email",
    "contact_email",
    "phone",
    "contact_phone",
    "subject",
    "message",
    "body",
    "name",
    "iban",
}
TOKEN_COMPARE_WORDS = ("token", "code", "secret", "password", "hash")
SENSITIVE_COMPARE_NAMES = {
    "email_verify_code",
    "verify_code",
    "verify_hash",
    "reset_code",
    "reset_hash",
    "reset_token",
    "token_hash",
    "password_hash",
    "secret",
}


@dataclass
class Finding:
    rule: str
    path: str
    line: int
    message: str


def _iter_py_files() -> Iterable[Path]:
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            yield path


def _full_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _full_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def _contains_sensitive_compare_name(node: ast.AST) -> bool:
    def _parts(text: str) -> list[str]:
        return [p for p in re.split(r"[^a-z0-9]+", text.lower()) if p]

    if isinstance(node, ast.Name):
        token = node.id.lower()
        if token in SENSITIVE_COMPARE_NAMES:
            return True
        joined = "_".join(_parts(token))
        return joined in SENSITIVE_COMPARE_NAMES
    if isinstance(node, ast.Attribute):
        attr = node.attr.lower()
        if attr in SENSITIVE_COMPARE_NAMES:
            return True
        joined = "_".join(_parts(attr))
        if joined in SENSITIVE_COMPARE_NAMES:
            return True
        return _contains_sensitive_compare_name(node.value)
    if isinstance(node, ast.Subscript):
        return _contains_sensitive_compare_name(
            node.value
        ) or _contains_sensitive_compare_name(node.slice)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            token = node.value.lower()
            if token in SENSITIVE_COMPARE_NAMES:
                return True
            joined = "_".join(_parts(token))
            return joined in SENSITIVE_COMPARE_NAMES
    return False


class _Visitor(ast.NodeVisitor):
    def __init__(self, path: Path):
        self.path = path
        self.findings: list[Finding] = []

    def _add(self, rule: str, node: ast.AST, message: str) -> None:
        self.findings.append(
            Finding(
                rule=rule,
                path=str(self.path),
                line=int(getattr(node, "lineno", 1)),
                message=message,
            )
        )

    def visit_Call(self, node: ast.Call) -> None:
        fn = _full_name(node.func)
        base_fn = fn.split(".")[-1].lower()

        if base_fn == "event_append":
            self._check_event_append(node)
        if fn.startswith("subprocess.") or fn == "subprocess":
            self._check_subprocess(node, fn)

        self.generic_visit(node)

    def _check_event_append(self, node: ast.Call) -> None:
        payload_kw = None
        for kw in node.keywords:
            if kw.arg == "payload":
                payload_kw = kw
                break
        if payload_kw is None:
            return
        if not isinstance(payload_kw.value, ast.Dict):
            return
        for key in payload_kw.value.keys:
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            key_name = key.value.strip().lower()
            if "redacted" in key_name:
                continue
            if key_name in EVENTLOG_FORBIDDEN_KEYS:
                self._add(
                    "eventlog_pii_key",
                    key,
                    f"event_append payload key '{key_name}' is not allowed (PII risk).",
                )

    def _check_subprocess(self, node: ast.Call, fn: str) -> None:
        run_like = fn in {
            "subprocess.run",
            "subprocess.call",
            "subprocess.check_call",
            "subprocess.check_output",
            "subprocess.Popen",
        }
        if not run_like:
            return

        has_shell = False
        shell_is_false = False
        has_timeout = False
        for kw in node.keywords:
            if kw.arg == "shell":
                has_shell = True
                if isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    shell_is_false = True
            if kw.arg == "timeout":
                has_timeout = True

        if not has_shell or not shell_is_false:
            self._add(
                "subprocess_shell",
                node,
                f"{fn} must set shell=False explicitly.",
            )
        if fn != "subprocess.check_output" and not has_timeout:
            self._add(
                "subprocess_timeout",
                node,
                f"{fn} should set an explicit timeout.",
            )

    def visit_Compare(self, node: ast.Compare) -> None:
        has_eq = any(isinstance(op, ast.Eq | ast.NotEq) for op in node.ops)
        if has_eq:
            targets = [node.left, *node.comparators]
            if any(_contains_sensitive_compare_name(item) for item in targets):
                self._add(
                    "token_compare",
                    node,
                    "Token/code/hash comparison should use secrets.compare_digest().",
                )
        self.generic_visit(node)


def run_scan() -> list[Finding]:
    findings: list[Finding] = []
    for path in _iter_py_files():
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            findings.append(
                Finding(
                    rule="syntax_error",
                    path=str(path),
                    line=int(getattr(exc, "lineno", 1) or 1),
                    message="Could not parse file during security scan.",
                )
            )
            continue
        visitor = _Visitor(path)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    return findings


def main() -> int:
    findings = run_scan()
    payload = {
        "ok": not findings,
        "count": len(findings),
        "findings": [
            {"rule": f.rule, "path": f.path, "line": f.line, "message": f.message}
            for f in findings
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
