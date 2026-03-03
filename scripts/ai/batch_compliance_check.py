#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path


DOMAINS = [
    "dashboard",
    "upload",
    "emailpostfach",
    "messenger",
    "kalender",
    "aufgaben",
    "zeiterfassung",
    "projekte",
    "excel-docs-visualizer",
    "einstellungen",
    "floating-widget-chatbot",
]


def run_cmd(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    cp = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )
    merged = (cp.stdout or "") + (("\n" + cp.stderr) if cp.stderr else "")
    return cp.returncode, merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gemini compliance checks for all domains")
    parser.add_argument(
        "--stamp",
        default=datetime.now().strftime("%Y%m%d_%H%M%S"),
        help="Output timestamp",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    fleet_root = root.parent
    py = root / ".build_venv" / "bin" / "python"
    wrapper = root / "scripts" / "ai" / "gemini_cli.py"

    summary_rows: list[str] = []
    for domain in DOMAINS:
        wt = fleet_root / "worktrees" / domain
        report = wt / "docs" / "reviews" / f"{domain}_compliance_{args.stamp}.md"
        wt.joinpath("docs", "reviews").mkdir(parents=True, exist_ok=True)

        prompt = (
            "Pruefe diese Domain auf Sovereign-11 Compliance. "
            "Antworte strikt mit den Abschnitten: "
            "Current State, Findings (P0/P1/P2), First 3 Safe Commits, Open Questions. "
            "Konzentriere dich auf Zero-CDN, White-Mode, HTMX, Domain-Ownership, Tests."
        )

        cmd = [
            str(py),
            str(wrapper),
            "--domain",
            domain,
            "--cwd",
            str(wt),
            "--output",
            str(report),
            "--approval-mode",
            "yolo",
            prompt,
        ]
        rc, out = run_cmd(cmd, cwd=root)
        status = "OK" if rc == 0 and report.exists() and report.stat().st_size > 0 else "FAIL"
        summary_rows.append(f"- {domain}: {status} ({report})")
        if status == "FAIL":
            # Write failure details into the report path to keep diagnostics local.
            report.write_text(out or f"gemini wrapper failed with rc={rc}\n", encoding="utf-8")

    summary = root / "docs" / "reviews" / f"batch_compliance_{args.stamp}.md"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        "# Batch Compliance Summary\n\n" + "\n".join(summary_rows) + "\n",
        encoding="utf-8",
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

