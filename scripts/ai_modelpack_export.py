#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.ai.modelpack import create_model_pack

    parser = argparse.ArgumentParser(
        description="Export local Ollama models into a portable KUKANILEA modelpack."
    )
    parser.add_argument(
        "--out",
        default="",
        help="Output file path (.tar.gz). If empty, a timestamped file is created.",
    )
    parser.add_argument(
        "--models-dir",
        default="",
        help="Optional source models directory (defaults to OLLAMA_MODELS or ~/.ollama/models).",
    )
    args = parser.parse_args()

    out_path = Path(args.out).expanduser() if str(args.out).strip() else Path(".")
    result = create_model_pack(
        pack_path=out_path,
        source_models_dir=(str(args.models_dir).strip() or None),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
