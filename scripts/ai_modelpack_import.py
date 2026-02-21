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
    from app.ai.modelpack import import_model_pack

    parser = argparse.ArgumentParser(
        description="Import a KUKANILEA modelpack into local Ollama models storage."
    )
    parser.add_argument(
        "--pack",
        required=True,
        help="Path to modelpack (.tar.gz) created by ai_modelpack_export.py.",
    )
    parser.add_argument(
        "--models-dir",
        default="",
        help="Optional destination models directory (defaults to OLLAMA_MODELS or ~/.ollama/models).",
    )
    args = parser.parse_args()

    result = import_model_pack(
        pack_path=args.pack,
        destination_models_dir=(str(args.models_dir).strip() or None),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
