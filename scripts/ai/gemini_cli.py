#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


NOISE_PREFIXES = (
    "YOLO mode is enabled.",
    "Loaded cached credentials.",
    "Loading extension:",
    "Server '",
    "Error during discovery for MCP server",
)


def read_text(path: Path, max_chars: int = 20000) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[...truncated...]"


def sanitize(raw: str) -> str:
    lines: list[str] = []
    for line in raw.splitlines():
        if any(line.startswith(prefix) for prefix in NOISE_PREFIXES):
            continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def build_prompt(
    root: Path,
    user_prompt: str,
    domain: str | None,
    context_files: list[Path],
) -> str:
    parts: list[str] = []

    alignment = root / "docs" / "ai" / "GEMINI_ALIGNMENT_PROMPT.md"
    if alignment.exists():
        parts.append("## SYSTEM ALIGNMENT\n" + read_text(alignment))

    if domain:
        parts.append(f"## DOMAIN\n{domain}")
        scope = root / "docs" / "scopes" / f"{domain}.md"
        if scope.exists():
            parts.append("## DOMAIN SCOPE\n" + read_text(scope, max_chars=12000))

    for ctx in context_files:
        if ctx.exists():
            parts.append(f"## CONTEXT FILE: {ctx}\n" + read_text(ctx, max_chars=12000))

    parts.append("## TASK\n" + user_prompt.strip())
    return "\n\n".join(parts).strip() + "\n"


def run_gemini(
    prompt: str,
    approval_mode: str,
    cwd: Path | None,
    timeout_seconds: int,
) -> tuple[int, str]:
    gemini_bin = shutil.which("gemini")
    if not gemini_bin:
        fallback = Path("/opt/homebrew/bin/gemini")
        if fallback.exists():
            gemini_bin = str(fallback)
    if not gemini_bin:
        return 127, "[error] gemini binary not found in PATH\n"

    cmd = [
        gemini_bin,
        "-p",
        prompt,
        "--output-format",
        "text",
        "--approval-mode",
        approval_mode,
    ]
    try:
        cp = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        merged = (cp.stdout or "") + (("\n" + cp.stderr) if cp.stderr else "")
        return cp.returncode, merged
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        err = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        merged = (out + ("\n" + err if err else "")).strip()
        if merged:
            merged += "\n"
        merged += f"[timeout] gemini command exceeded {timeout_seconds}s\n"
        return 124, merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KUKANILEA Gemini CLI wrapper")
    parser.add_argument("prompt", nargs="?", help="Prompt text")
    parser.add_argument("--prompt-file", help="Read prompt text from file")
    parser.add_argument("--domain", help="Domain slug (e.g. upload)")
    parser.add_argument(
        "--context-file",
        action="append",
        default=[],
        help="Additional context files to inject",
    )
    parser.add_argument("--output", help="Write sanitized output to file")
    parser.add_argument("--log", help="Write raw output and metadata to file")
    parser.add_argument("--cwd", help="Working directory for gemini command")
    parser.add_argument(
        "--approval-mode",
        default="yolo",
        choices=["default", "yolo"],
        help="Gemini approval mode",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Do not sanitize output (keep gemini bootstrap lines)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help="Timeout for gemini subprocess",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]

    user_prompt = args.prompt or ""
    if args.prompt_file:
        user_prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    if not user_prompt.strip():
        print("missing prompt: provide positional prompt or --prompt-file", file=sys.stderr)
        return 2

    context_files = [Path(p) for p in args.context_file]
    final_prompt = build_prompt(root, user_prompt, args.domain, context_files)
    cwd = Path(args.cwd) if args.cwd else None

    try:
        rc, raw = run_gemini(
            final_prompt,
            approval_mode=args.approval_mode,
            cwd=cwd,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as exc:  # defensive catch for orchestration reliability
        rc = 1
        raw = f"[error] unexpected gemini wrapper failure: {exc}\n"
    out = raw if args.raw else sanitize(raw)

    if args.log:
        log_path = Path(args.log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"returncode={rc}\n"
            f"domain={args.domain or ''}\n"
            f"cwd={cwd or ''}\n"
            f"\n--- raw ---\n{raw}\n",
            encoding="utf-8",
        )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)

    if rc != 0:
        return rc
    if not out.strip():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
