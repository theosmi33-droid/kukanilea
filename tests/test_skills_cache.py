from __future__ import annotations

import json
from pathlib import Path

from app.config import Config
from app.skills.cache import write_cache
from app.skills.model import SkillImportResult


def test_write_cache_creates_folder_and_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path / "ud")

    result = SkillImportResult(
        name="demo",
        source_url="https://github.com/acme/repo",
        ref="main",
        resolved_commit="c" * 40,
        files={
            "skills/demo/SKILL.md": b"# Demo\n",
            "skills/demo/README.md": b"readme",
        },
        manifest={
            "files": [
                {"path": "skills/demo/SKILL.md", "sha256": "x", "bytes_len": 7},
                {"path": "skills/demo/README.md", "sha256": "y", "bytes_len": 6},
            ]
        },
    )

    cache_key, folder, manifest = write_cache(result)

    assert cache_key.startswith("demo_")
    assert folder.exists()
    assert (folder / "skills/demo/SKILL.md").exists()
    assert manifest["meta"]["status"] == "quarantine"

    saved = json.loads((folder / "manifest.json").read_text())
    assert saved["meta"]["cache_key"] == cache_key
    assert len(saved["files"]) == 2
