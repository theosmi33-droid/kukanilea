from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from app.ai.modelpack import create_model_pack, import_model_pack


def test_modelpack_create_and_import_roundtrip(tmp_path: Path) -> None:
    source = tmp_path / "source_models"
    (source / "blobs").mkdir(parents=True)
    (source / "manifests").mkdir(parents=True)
    (source / "manifests" / "registry.json").write_text(
        '{"schemaVersion":2}',
        encoding="utf-8",
    )
    (source / "blobs" / "sha256-abc").write_bytes(b"demo")

    pack = tmp_path / "packs" / "offline-pack.tar.gz"
    exported = create_model_pack(pack_path=pack, source_models_dir=source)
    assert exported["ok"] is True
    assert pack.exists()

    dest = tmp_path / "dest_models"
    imported = import_model_pack(pack_path=pack, destination_models_dir=dest)
    assert imported["ok"] is True
    assert imported["extracted_files"] >= 2
    assert (dest / "manifests" / "registry.json").exists()
    assert (dest / "blobs" / "sha256-abc").read_bytes() == b"demo"
    assert imported.get("metadata", {}).get("format") == "kukanilea-ollama-modelpack-v1"


def test_modelpack_rejects_unsafe_members(tmp_path: Path) -> None:
    pack = tmp_path / "unsafe.tar.gz"
    with tarfile.open(pack, mode="w:gz") as tar:
        payload = b"bad"
        info = tarfile.TarInfo(name="../escape.txt")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    with pytest.raises(ValueError, match="unsafe_tar_member"):
        import_model_pack(pack_path=pack, destination_models_dir=tmp_path / "dest")
