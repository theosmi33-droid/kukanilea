from __future__ import annotations

import io
from pathlib import Path

from werkzeug.datastructures import FileStorage

from app.core.upload_pipeline import MAX_FILE_SIZE, save_upload_stream


def test_save_upload_stream_writes_content(tmp_path: Path) -> None:
    dest = tmp_path / "in" / "doc.txt"
    payload = b"A" * (256 * 1024)
    fs = FileStorage(stream=io.BytesIO(payload), filename="doc.txt")

    written = save_upload_stream(fs, dest)

    assert written == len(payload)
    assert dest.read_bytes() == payload


def test_save_upload_stream_enforces_max_size(tmp_path: Path) -> None:
    dest = tmp_path / "in" / "big.txt"
    payload = b"B" * (MAX_FILE_SIZE + 1)
    fs = FileStorage(stream=io.BytesIO(payload), filename="big.txt")

    try:
        save_upload_stream(fs, dest)
        assert False, "Expected ValueError(file_too_large)"
    except ValueError as exc:
        assert str(exc) == "file_too_large"
