from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from . import postfach_imap, postfach_store


def sync_all_accounts(
    db_path: Path,
    *,
    tenant_id: str,
    limit_per_account: int = 50,
    auto_download_attachments: bool = True,
) -> dict[str, Any]:
    postfach_store.ensure_postfach_schema(db_path)
    results: list[dict[str, Any]] = []
    accounts = postfach_store.list_accounts(db_path, tenant_id)
    for account in accounts:
        account_id = str(account.get("id") or "")
        if not account_id:
            continue
        try:
            res = postfach_imap.sync_account(
                db_path,
                tenant_id=tenant_id,
                account_id=account_id,
                limit=limit_per_account,
                auto_download_attachments=auto_download_attachments,
            )
        except Exception:
            res = {"ok": False, "reason": "sync_exception", "imported": 0, "duplicates": 0}
        results.append({"account_id": account_id, "result": res})

    imported = sum(int((r.get("result") or {}).get("imported") or 0) for r in results)
    duplicates = sum(int((r.get("result") or {}).get("duplicates") or 0) for r in results)
    failed = len([r for r in results if not bool((r.get("result") or {}).get("ok"))])
    return {
        "ok": failed == 0,
        "reason": "ok" if failed == 0 else "partial_failure",
        "accounts_total": len(results),
        "accounts_failed": failed,
        "imported": imported,
        "duplicates": duplicates,
        "results": results,
    }


class MailSyncEngine:
    def __init__(
        self,
        *,
        db_path: Path,
        tenant_id: str,
        interval_seconds: int = 300,
        limit_per_account: int = 50,
        auto_download_attachments: bool = True,
    ) -> None:
        self.db_path = db_path
        self.tenant_id = str(tenant_id or "").strip()
        self.interval_seconds = max(30, int(interval_seconds or 300))
        self.limit_per_account = max(1, min(int(limit_per_account or 50), 500))
        self.auto_download_attachments = bool(auto_download_attachments)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def tick(self) -> dict[str, Any]:
        return sync_all_accounts(
            self.db_path,
            tenant_id=self.tenant_id,
            limit_per_account=self.limit_per_account,
            auto_download_attachments=self.auto_download_attachments,
        )

    def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception:
                # Offline/network errors must never crash the loop.
                pass
            self._stop_event.wait(self.interval_seconds)


def run_background_loop(
    *,
    db_path: Path,
    tenant_id: str,
    stop_event: threading.Event,
    interval_seconds: int = 300,
    limit_per_account: int = 50,
    auto_download_attachments: bool = True,
) -> None:
    engine = MailSyncEngine(
        db_path=db_path,
        tenant_id=tenant_id,
        interval_seconds=interval_seconds,
        limit_per_account=limit_per_account,
        auto_download_attachments=auto_download_attachments,
    )
    engine._stop_event = stop_event
    while not stop_event.is_set():
        try:
            engine.tick()
        except Exception:
            pass
        stop_event.wait(engine.interval_seconds)
