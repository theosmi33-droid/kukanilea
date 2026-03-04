from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

REQUIRED_TOOLS = ("python", "pip", "venv", "sqlite3", "rg", "gh", "playwright")


@dataclass
class DoctorResult:
    check: str
    ok: bool
    detail: str


def _normalize_version(version: str) -> str:
    clean = version.strip()
    if not clean:
        return clean
    # Allow either "3.12" or "3.12.0" in .python-version.
    parts = clean.split(".")
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return clean


def check_python_version(expected_file: Path, current: tuple[int, int, int] | None = None) -> tuple[bool, str]:
    if not expected_file.exists():
        return False, f"Missing {expected_file}; define the project Python runtime first."

    declared = expected_file.read_text(encoding="utf-8").strip()
    if not declared:
        return False, f"{expected_file} is empty; expected a version such as 3.12.0."

    current_version = current if current is not None else sys.version_info[:3]
    declared_mm = _normalize_version(declared)
    active_mm = f"{current_version[0]}.{current_version[1]}"
    if active_mm != declared_mm:
        return (
            False,
            (
                "Python version mismatch: project requires "
                f"{declared} from {expected_file}, but active interpreter is "
                f"{current_version[0]}.{current_version[1]}.{current_version[2]}."
            ),
        )

    return True, f"Python {declared} requirement satisfied by active {active_mm}."


def _tool_exists(name: str) -> bool:
    if name == "python":
        return True
    if name == "venv":
        return True
    return shutil.which(name) is not None


def _probe_sqlite() -> tuple[bool, str]:
    try:
        sqlite3.connect(":memory:").close()
        return True, "sqlite3 module import/connect OK"
    except sqlite3.Error as exc:  # pragma: no cover - defensive
        return False, f"sqlite3 check failed: {exc}"


def _probe_playwright_cli() -> tuple[bool, str]:
    if shutil.which("playwright"):
        return True, "playwright CLI found"

    cmd = [sys.executable, "-m", "playwright", "--version"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        version = proc.stdout.strip() or proc.stderr.strip()
        return True, f"playwright module available ({version})"
    return False, "playwright CLI/module missing"


def collect_doctor_results(repo_root: Path, required_tools: Iterable[str] = REQUIRED_TOOLS) -> list[DoctorResult]:
    checks: list[DoctorResult] = []

    version_ok, version_detail = check_python_version(repo_root / ".python-version")
    checks.append(DoctorResult(check="python-version", ok=version_ok, detail=version_detail))

    for tool in required_tools:
        if tool == "sqlite3":
            ok, detail = _probe_sqlite()
        elif tool == "playwright":
            ok, detail = _probe_playwright_cli()
        else:
            ok = _tool_exists(tool)
            detail = f"{tool} available" if ok else f"{tool} not found in PATH"
        checks.append(DoctorResult(check=tool, ok=ok, detail=detail))

    build_venv = repo_root / ".build_venv"
    checks.append(
        DoctorResult(
            check=".build_venv",
            ok=build_venv.exists(),
            detail=f"{build_venv} exists" if build_venv.exists() else f"{build_venv} missing",
        )
    )

    return checks


def summarize_exit_code(results: Iterable[DoctorResult]) -> int:
    has_failures = any(not item.ok for item in results)
    return 2 if has_failures else 0


def to_json_payload(results: Iterable[DoctorResult]) -> str:
    items = [asdict(item) for item in results]
    payload = {
        "ok": all(item["ok"] for item in items),
        "checks": items,
    }
    return json.dumps(payload, indent=2)


if __name__ == "__main__":
    root = Path(os.environ.get("KUKANILEA_REPO_ROOT", Path.cwd()))
    result_items = collect_doctor_results(root)
    print(to_json_payload(result_items))
    raise SystemExit(summarize_exit_code(result_items))
