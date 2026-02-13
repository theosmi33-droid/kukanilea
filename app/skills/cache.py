from __future__ import annotations

import json
from pathlib import Path

from app.skills.model import SkillImportResult
from app.skills.paths import cache_root, quarantine_root
from app.skills.util import ensure_dir, safe_join, utcnow_iso


def write_cache(import_result: SkillImportResult) -> tuple[str, Path, dict]:
    """Write fetched skill files to immutable cache folder and manifest.json."""
    ts = utcnow_iso().replace(":", "").replace("-", "")
    stamp = ts.split("+", 1)[0].replace("T", "T") + "Z"
    commit_short = (import_result.resolved_commit or import_result.ref)[:8]
    cache_key = f"{import_result.name}_{stamp}_{commit_short}"

    root = ensure_dir(cache_root())
    folder = root / cache_key
    if folder.exists():
        raise FileExistsError(f"cache_exists:{cache_key}")
    ensure_dir(folder)

    files_meta: list[dict] = []
    for rel_path, content in import_result.files.items():
        target = safe_join(folder, rel_path)
        ensure_dir(target.parent)
        target.write_bytes(content)
        file_row = next(
            (
                item
                for item in import_result.manifest.get("files", [])
                if item.get("path") == rel_path
            ),
            None,
        )
        files_meta.append(
            {
                "path": rel_path,
                "sha256": (file_row or {}).get("sha256", ""),
                "bytes_len": int((file_row or {}).get("bytes_len", len(content))),
            }
        )

    manifest = {
        "meta": {
            "name": import_result.name,
            "source_url": import_result.source_url,
            "ref": import_result.ref,
            "resolved_commit": import_result.resolved_commit,
            "fetched_at_utc": utcnow_iso(),
            "cache_key": cache_key,
            "status": "quarantine",
        },
        "cache_folder": str(folder),
        "files": sorted(files_meta, key=lambda x: x["path"]),
    }

    (folder / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )

    # prepare quarantine root for explicit workflows
    ensure_dir(quarantine_root())
    return cache_key, folder, manifest
