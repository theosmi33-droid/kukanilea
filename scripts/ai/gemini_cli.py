#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


NOISE_PREFIXES = (
    "YOLO mode is enabled.",
    "Loaded cached credentials.",
    "Loading extension:",
    "Server '",
    "Error during discovery for MCP server",
)

SAFE_APPROVAL_MODE = "default"
UNSAFE_APPROVAL_MODE = "yolo"
APPROVAL_MODE_CHOICES = [SAFE_APPROVAL_MODE, UNSAFE_APPROVAL_MODE]


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
    skip_alignment: bool,
) -> str:
    parts: list[str] = []

    if not skip_alignment:
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
    model: str | None,
    extensions: list[str],
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
    if model:
        cmd.extend(["-m", model])
    for ext in extensions:
        clean = ext.strip()
        if clean:
            cmd.extend(["--extensions", clean])
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


def resolve_approval_mode(cli_value: str | None) -> str:
    """Require explicit approval mode via CLI flag or env var."""
    mode = (cli_value or os.environ.get("GEMINI_APPROVAL_MODE") or "").strip().lower()
    if mode not in APPROVAL_MODE_CHOICES:
        choices = ", ".join(APPROVAL_MODE_CHOICES)
        raise ValueError(
            "missing explicit approval mode. "
            "Provide --approval-mode or set GEMINI_APPROVAL_MODE "
            f"to one of: {choices}"
        )
    return mode


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
        choices=APPROVAL_MODE_CHOICES,
        help=(
            "Gemini approval mode. Explicitly required via this flag or "
            "GEMINI_APPROVAL_MODE environment variable."
        ),
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
    parser.add_argument("--model", help="Gemini model override")
    parser.add_argument(
        "--extension",
        action="append",
        default=[],
        help="Enable only the given extension name (repeatable)",
    )
    parser.add_argument(
        "--require-main",
        action="store_true",
        help="Fail if current git branch is not main",
    )
    parser.add_argument(
        "--skip-alignment",
        action="store_true",
        help="Skip injection of GEMINI_ALIGNMENT_PROMPT.md for faster focused runs",
    )
    return parser.parse_args()


def enforce_main_branch(cwd: Path | None, root: Path) -> tuple[bool, str]:
    repo_dir = cwd or root
    try:
        cp = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_dir),
            text=True,
            capture_output=True,
            check=False,
            timeout=8,
        )
    except Exception as exc:
        return False, f"[error] could not verify current branch: {exc}"
    if cp.returncode != 0:
        msg = (cp.stderr or cp.stdout or "").strip()
        return False, f"[error] git branch check failed: {msg or 'unknown git error'}"
    branch = (cp.stdout or "").strip()
    if branch != "main":
        return False, (
            f"[error] main-only policy active: current branch is '{branch}', required 'main'."
        )
    return True, ""


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]

    try:
        approval_mode = resolve_approval_mode(args.approval_mode)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    if approval_mode == UNSAFE_APPROVAL_MODE:
        print(
            "[warn] Running Gemini in YOLO mode (unsafe for unattended production use).",
            file=sys.stderr,
        )

    user_prompt = args.prompt or ""
    if args.prompt_file:
        user_prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    if not user_prompt.strip():
        print("missing prompt: provide positional prompt or --prompt-file", file=sys.stderr)
        return 2

    context_files = [Path(p) for p in args.context_file]
    final_prompt = build_prompt(
        root=root,
        user_prompt=user_prompt,
        domain=args.domain,
        context_files=context_files,
        skip_alignment=args.skip_alignment,
    )
    cwd = Path(args.cwd) if args.cwd else None
    extensions = args.extension or []

    if args.require_main:
        ok, message = enforce_main_branch(cwd, root)
        if not ok:
            print(message, file=sys.stderr)
            return 2

    try:
        rc, raw = run_gemini(
            final_prompt,
            approval_mode=approval_mode,
            model=args.model,
            extensions=extensions,
            cwd=cwd,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as exc:  # defensive catch for orchestration reliability
        rc = 1
        raw = f"[error] unexpected gemini wrapper failure: {exc}\n"
    out = raw if args.raw else sanitize(raw)

    if args.log:
        started_at = datetime.now(UTC).isoformat()
        log_path = Path(args.log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"returncode={rc}\n"
            f"timestamp_utc={started_at}\n"
            f"domain={args.domain or ''}\n"
            f"cwd={cwd or ''}\n"
            f"approval_mode={approval_mode}\n"
            f"sanitized_output_bytes={len(out.encode('utf-8'))}\n"
            f"raw_output_bytes={len(raw.encode('utf-8'))}\n"
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
        print("[error] gemini produced empty output after sanitization", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
