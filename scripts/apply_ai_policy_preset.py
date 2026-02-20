#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def _preset_local_only() -> dict[str, Any]:
    return {
        "default": {
            "allow_local": True,
            "allow_cloud": False,
        }
    }


def _preset_balanced() -> dict[str, Any]:
    return {
        "default": {
            "allow_local": True,
            "allow_cloud": False,
        },
        "roles": {
            "OPERATOR": {"allow_cloud": True},
            "ADMIN": {"allow_cloud": True},
            "DEV": {"allow_cloud": True},
            "READONLY": {"allow_cloud": False},
        },
    }


def _preset_reliability_max() -> dict[str, Any]:
    return {
        "default": {
            "allow_local": True,
            "allow_cloud": True,
        },
        "roles": {
            "READONLY": {"allow_cloud": False},
            "OPERATOR": {"allow_providers": ["vllm", "lmstudio", "ollama", "groq"]},
            "ADMIN": {
                "allow_providers": [
                    "vllm",
                    "lmstudio",
                    "ollama",
                    "groq",
                    "anthropic",
                    "gemini",
                ]
            },
            "DEV": {
                "allow_providers": [
                    "vllm",
                    "lmstudio",
                    "ollama",
                    "groq",
                    "anthropic",
                    "gemini",
                    "openai_compat",
                    "openai_compat_fallback",
                ]
            },
        },
    }


PRESETS = {
    "local_only": _preset_local_only,
    "balanced": _preset_balanced,
    "reliability_max": _preset_reliability_max,
}


def _default_policy_path() -> Path:
    root = Path(
        os.environ.get(
            "KUKANILEA_USER_DATA_ROOT",
            str(Path.home() / "Library" / "Application Support" / "KUKANILEA"),
        )
    )
    return root / "ai_provider_policy.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Schreibt ein AI-Policy-Preset als JSON-Datei (serverseitige Provider-Policy)."
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS.keys()),
        default="balanced",
        help="Policy-Preset.",
    )
    parser.add_argument(
        "--out",
        default=str(_default_policy_path()),
        help="Zielpfad der Policy-Datei.",
    )
    parser.add_argument(
        "--print-env",
        action="store_true",
        help="Gibt passende Export-Zeile fuer KUKANILEA_AI_PROVIDER_POLICY_FILE aus.",
    )
    args = parser.parse_args()

    policy = PRESETS[args.preset]()
    out = Path(str(args.out)).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"ok": True, "preset": args.preset, "path": str(out)}, ensure_ascii=False
        )
    )
    if args.print_env:
        print(f'export KUKANILEA_AI_PROVIDER_POLICY_FILE="{out}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
