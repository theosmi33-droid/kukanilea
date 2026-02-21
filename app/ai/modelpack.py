from __future__ import annotations

import io
import json
import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ollama_models_dir() -> Path:
    raw = str(os.environ.get("OLLAMA_MODELS") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".ollama" / "models"


def _safe_pack_name(path: str) -> str:
    token = str(path or "").strip().replace(" ", "_")
    if not token:
        token = f"kukanilea-ollama-modelpack-{_now_iso().replace(':', '-')}"
    if not token.endswith(".tar.gz"):
        token = f"{token}.tar.gz"
    return token


def create_model_pack(
    *,
    pack_path: str | Path,
    source_models_dir: str | Path | None = None,
) -> dict[str, Any]:
    src = Path(source_models_dir) if source_models_dir else ollama_models_dir()
    src = src.expanduser().resolve()
    if not src.exists() or not src.is_dir():
        raise FileNotFoundError(f"models_dir_not_found:{src}")

    out = Path(pack_path).expanduser()
    if out.is_dir():
        out = out / _safe_pack_name("")
    out.parent.mkdir(parents=True, exist_ok=True)

    file_count = 0
    total_bytes = 0
    for path in src.rglob("*"):
        if path.is_file():
            file_count += 1
            total_bytes += int(path.stat().st_size)

    metadata = {
        "created_at": _now_iso(),
        "source_models_dir": str(src),
        "file_count": file_count,
        "total_bytes": total_bytes,
        "format": "kukanilea-ollama-modelpack-v1",
    }

    with tarfile.open(str(out), mode="w:gz") as tar:
        payload = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
        info = tarfile.TarInfo(name="metadata.json")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
        tar.add(str(src), arcname="models", recursive=True)

    return {
        "ok": True,
        "pack_path": str(out),
        "file_count": file_count,
        "total_bytes": total_bytes,
    }


def _is_safe_member(name: str) -> bool:
    token = str(name or "")
    if token.startswith("/") or token.startswith("\\"):
        return False
    if ".." in Path(token).parts:
        return False
    return token in {"metadata.json", "models", "models/"} or token.startswith(
        "models/"
    )


def import_model_pack(
    *,
    pack_path: str | Path,
    destination_models_dir: str | Path | None = None,
) -> dict[str, Any]:
    pack = Path(pack_path).expanduser().resolve()
    if not pack.exists() or not pack.is_file():
        raise FileNotFoundError(f"model_pack_not_found:{pack}")

    dest = (
        Path(destination_models_dir) if destination_models_dir else ollama_models_dir()
    )
    dest = dest.expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)

    extracted_files = 0
    metadata: dict[str, Any] = {}
    with tarfile.open(str(pack), mode="r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            if not _is_safe_member(member.name):
                raise ValueError(f"unsafe_tar_member:{member.name}")
        for member in members:
            if member.islnk() or member.issym():
                raise ValueError(f"unsupported_tar_member_type:{member.name}")
            if member.name == "metadata.json":
                stream = tar.extractfile(member)
                if stream is not None:
                    try:
                        payload = json.loads(stream.read().decode("utf-8"))
                    except Exception:
                        payload = {}
                    if isinstance(payload, dict):
                        metadata = payload
                continue
            if member.name in {"models", "models/"}:
                continue
            rel = Path(member.name).relative_to("models")
            target = (dest / rel).resolve()
            if not str(target).startswith(str(dest)):
                raise ValueError("unsafe_target_path")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ValueError(f"unsupported_tar_member_type:{member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = tar.extractfile(member)
            if stream is None:
                raise ValueError(f"cannot_extract_member:{member.name}")
            with target.open("wb") as fh:
                fh.write(stream.read())
            if isinstance(member.mode, int):
                try:
                    os.chmod(target, member.mode)
                except Exception:
                    pass
            if member.isfile():
                extracted_files += 1

    return {
        "ok": True,
        "pack_path": str(pack),
        "destination_models_dir": str(dest),
        "extracted_files": extracted_files,
        "metadata": metadata,
    }
