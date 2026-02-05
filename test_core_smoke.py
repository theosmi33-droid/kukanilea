#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import shutil
from pathlib import Path

import pytest

try:
    import tophandwerk_core as core
except ModuleNotFoundError:
    pytest.skip("tophandwerk_core not available in this repo", allow_module_level=True)


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    # --- 0) Isoliertes Test-Setup (SAFE) ---
    tmp = Path.cwd() / "_THW_TEST_SANDBOX"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    # Patch core paths to sandbox (so we don't touch ~/Tophandwerk_*)
    core.EINGANG = tmp / "Eingang"
    core.BASE_PATH = tmp / "Kundenablage"
    core.PENDING_DIR = tmp / "Pending"
    core.DONE_DIR = tmp / "Done"
    core.DB_PATH = tmp / "Tophandwerk_DB.sqlite3"

    core._bootstrap_dirs()
    core.db_init()

    print("OK: sandbox + db_init")

    # --- 1) Create dummy input file ---
    src = core.EINGANG / "dummy_rechnung.txt"
    src.write_text(
        "Rechnung\n"
        "Kunden-Nr: 12345\n"
        "Datum: 12.01.2026\n"
        "Max Mustermann\n"
        "Musterstraße 1\n"
        "12689 Berlin\n"
        "Betrag: 100,00 EUR\n",
        encoding="utf-8",
    )
    _assert(src.exists(), "dummy file missing")
    print("OK: created input file")

    # --- 2) Background analysis -> pending ---
    token = core.start_background_analysis(src)
    _assert(token, "no token")
    print("OK: analysis started, token =", token)

    # Wait for READY (max ~8s)
    ready = False
    for _ in range(80):
        d = core.read_pending(token) or {}
        if d.get("status") == "READY":
            ready = True
            break
        if d.get("status") == "ERROR":
            raise RuntimeError(f"Analysis ERROR: {d.get('error')}")
        time.sleep(0.1)

    _assert(ready, "analysis not ready in time")
    d = core.read_pending(token) or {}
    print("OK: analysis READY")
    print("  doctype_suggested:", d.get("doctype_suggested"))
    print("  doc_date_suggested:", d.get("doc_date_suggested"))
    print("  kdnr_ranked:", d.get("kdnr_ranked")[:3])
    print("  name_suggestions:", d.get("name_suggestions")[:1])
    print("  addr_suggestions:", d.get("addr_suggestions")[:1])
    print("  plzort_suggestions:", d.get("plzort_suggestions")[:1])

    # --- 3) Process with answers -> move into Kundenablage + index ---
    answers = {
        "kdnr": "12345",
        "use_existing": "",  # or folder path
        "name": "Max Mustermann",
        "addr": "Musterstraße 1",
        "plzort": "12689 Berlin",
        "doctype": "RECHNUNG",
        "document_date": "12.01.2026",
    }

    folder, target, created = core.process_with_answers(src, answers)
    _assert(folder.exists() and folder.is_dir(), "target folder missing")
    _assert(target.exists() and target.is_file(), "target file missing")
    _assert(not src.exists(), "source should be moved/deleted")
    print("OK: processed ->", target)
    print("  created_new_object =", created)

    # Expect filename prefix RE_ and date present
    _assert(target.name.startswith("RE_"), "filename should start with RE_")
    _assert("2026-01-12" in target.name, "date should be normalized to YYYY-MM-DD in filename")

    # --- 4) Dedupe test: process same content again -> should NOT create new file ---
    src2 = core.EINGANG / "dummy_rechnung_copy.txt"
    src2.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")

    folder2, target2, created2 = core.process_with_answers(src2, answers)
    _assert(target2.exists(), "target2 missing")
    _assert(target2 == target, "dedupe should point to same target path (same bytes)")
    _assert(not src2.exists(), "src2 should be removed")
    print("OK: dedupe same bytes (no new version file)")

    # --- 5) Version test: changed bytes -> should create _v2 file ---
    src3 = core.EINGANG / "dummy_rechnung_changed.txt"
    src3.write_text(target.read_text(encoding="utf-8") + "\nNEU: Zusatzzeile\n", encoding="utf-8")

    folder3, target3, created3 = core.process_with_answers(src3, answers)
    _assert(target3.exists(), "target3 missing")
    _assert(target3.name != target.name, "changed bytes should produce a new filename")
    _assert("_v2" in target3.stem or "_v" in target3.stem, "should create version suffix")
    print("OK: versioning on changed bytes ->", target3.name)

    # --- 6) Search test ---
    res = core.assistant_search("Zusatzzeile", kdnr="12345", limit=10)
    _assert(isinstance(res, list), "search result not list")
    _assert(len(res) >= 1, "should find the changed doc text via search")
    print("OK: assistant_search hit count =", len(res))
    print("  top hit preview:", (res[0].get("preview") or "")[:120])

    # --- 7) Folder duplicate detector (sanity, should be empty or small) ---
    dups = core.detect_object_duplicates_for_kdnr("12345")
    _assert(isinstance(dups, list), "dups not list")
    print("OK: duplicate detector entries =", len(dups))

    print("\nALL TESTS PASSED ✅")
    print("Sandbox:", tmp)


if __name__ == "__main__":
    main()
