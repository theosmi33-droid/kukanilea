from __future__ import annotations

from pathlib import Path

from app.core import logic


def test_analyze_worker_writes_dlq_on_ocr_failure(monkeypatch, tmp_path: Path) -> None:
    src = tmp_path / "scan.pdf"
    src.write_bytes(b"%PDF-1.4\n")

    state = {
        "path": str(src),
        "tenant_suggested": "tenant-z",
        "status": "ANALYZING",
        "force_ocr": False,
    }

    writes = []
    dlq = []

    monkeypatch.setattr(logic, "read_pending", lambda _token: dict(state))

    def _write_pending(_token, payload):
        writes.append(payload)

    monkeypatch.setattr(logic, "write_pending", _write_pending)
    monkeypatch.setattr(logic, "_set_progress", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(logic, "_read_bytes", lambda _src: b"abc")
    monkeypatch.setattr(logic, "_sha256_bytes", lambda _b: "doc-hash")
    monkeypatch.setattr(logic, "_db_has_doc", lambda _doc_id: False)
    monkeypatch.setattr(logic, "_extract_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("ocr down")))

    def _dlq(file_path: Path, tenant_id: str, reason: str, context=None):
        dlq.append((file_path.name, tenant_id, reason, context or {}))

    monkeypatch.setattr("app.core.upload_pipeline.write_dead_letter_marker", _dlq)

    logic._analyze_worker("tok-1")

    assert dlq
    assert dlq[0][1] == "tenant-z"
    assert dlq[0][2] == "OCR_EXTRACTION_FAILED"
    assert writes
    assert writes[-1]["status"] == "ERROR"
    assert "ocr_extraction_failed" in writes[-1]["error"]


def test_start_index_warmup_thread_if_needed_limits_parallel_threads(monkeypatch) -> None:
    created_threads = []

    class _FakeThread:
        def __init__(self, target, daemon, name):
            self.target = target
            self.daemon = daemon
            self.name = name
            self._alive = False
            created_threads.append(self)

        def start(self):
            self._alive = True

        def is_alive(self):
            return self._alive

    monkeypatch.setattr(logic.threading, "Thread", _FakeThread)
    monkeypatch.setattr(logic, "_INDEX_WARMUP_THREAD", None)

    assert logic._start_index_warmup_thread_if_needed() is True
    assert len(created_threads) == 1
    assert created_threads[0].name == "kukanilea-index-warmup"

    # While active, no additional background index thread may be spawned.
    assert logic._start_index_warmup_thread_if_needed() is False
    assert len(created_threads) == 1

    # After the previous worker is no longer alive, a new one may start.
    created_threads[0]._alive = False
    assert logic._start_index_warmup_thread_if_needed() is True
    assert len(created_threads) == 2
