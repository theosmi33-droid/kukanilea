from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Protocol
from uuid import uuid4

from app.modules.mail.logic import classify_message, generate_reply_draft


class IngestionError(RuntimeError):
    pass


class ProviderAuthError(IngestionError):
    pass


class ProviderNetworkError(IngestionError):
    pass


class InboxProvider(Protocol):
    name: str

    def fetch_messages(self, *, tenant_id: str) -> list[dict[str, Any]]:
        ...


@dataclass
class StubInboxProvider:
    name: str = "imap_stub"
    mode: str = "ok"

    def fetch_messages(self, *, tenant_id: str) -> list[dict[str, Any]]:
        if self.mode == "auth_fail":
            raise ProviderAuthError("provider_auth_failed")
        if self.mode == "network_fail":
            raise ProviderNetworkError("provider_network_unavailable")
        now = datetime.now(UTC).isoformat()
        return [
            {
                "provider_message_id": f"{tenant_id}-{self.name}-welcome",
                "sender": "kontakt@example.com",
                "subject": "Willkommen im Postfach",
                "body": "Bitte melden Sie sich mit einem Statusupdate.",
                "received_at": now,
                "unread": True,
                "follow_up_due_at": now,
            }
        ]


@dataclass
class SMTPStubProvider:
    name: str = "smtp_stub"

    def send(self, *, to: str, subject: str, body: str) -> dict[str, Any]:
        return {
            "status": "sent",
            "provider": self.name,
            "provider_message_id": f"smtp-{uuid4().hex[:12]}",
            "to": to,
            "subject": subject,
            "body": body,
        }


ProviderFactory = Callable[[str], InboxProvider]


class EmailpostfachService:
    def __init__(
        self,
        *,
        db_path: str,
        inbox_provider_factory: ProviderFactory | None = None,
        smtp_provider: SMTPStubProvider | None = None,
        llm_draft_generator: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self._db_path = db_path
        self._inbox_provider_factory = inbox_provider_factory or (lambda _provider_name: StubInboxProvider())
        self._smtp_provider = smtp_provider or SMTPStubProvider()
        self._llm_draft_generator = llm_draft_generator

    def _db(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    def ingest(self, *, tenant_id: str, provider_name: str, actor: str) -> dict[str, Any]:
        provider = self._inbox_provider_factory(provider_name)
        try:
            messages = provider.fetch_messages(tenant_id=tenant_id)
        except (ProviderAuthError, ProviderNetworkError):
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise IngestionError(str(exc)) from exc

        inserted = 0
        with self._db() as con:
            for row in messages:
                con.execute(
                    """
                    INSERT OR REPLACE INTO emailpostfach_messages(
                        tenant_id, provider, provider_message_id, sender, subject, body,
                        received_at, unread, follow_up_due_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        tenant_id,
                        provider_name,
                        str(row.get("provider_message_id") or uuid4().hex),
                        str(row.get("sender") or ""),
                        str(row.get("subject") or ""),
                        str(row.get("body") or ""),
                        str(row.get("received_at") or self._now_iso()),
                        1 if bool(row.get("unread", True)) else 0,
                        str(row.get("follow_up_due_at") or "") or None,
                        self._now_iso(),
                    ),
                )
                inserted += 1
            con.execute(
                """
                INSERT INTO emailpostfach_audit(ts, tenant_id, username, action, target, details)
                VALUES (?,?,?,?,?,?)
                """,
                (self._now_iso(), tenant_id, actor, "emailpostfach.sync", provider_name, f"inserted={inserted}"),
            )
        return {"status": "ok", "provider": provider_name, "inserted": inserted, "last_sync": self._now_iso()}

    def summary(self, *, tenant_id: str) -> dict[str, Any]:
        with self._db() as con:
            unread_row = con.execute(
                "SELECT COUNT(*) AS c FROM emailpostfach_messages WHERE tenant_id=? AND unread=1", (tenant_id,)
            ).fetchone()
            follow_up_row = con.execute(
                """
                SELECT COUNT(*) AS c
                FROM emailpostfach_messages
                WHERE tenant_id=?
                  AND follow_up_due_at IS NOT NULL
                  AND follow_up_due_at <= ?
                """,
                (tenant_id, self._now_iso()),
            ).fetchone()
            last_sync_row = con.execute(
                """
                SELECT MAX(ts) AS last_sync
                FROM emailpostfach_audit
                WHERE tenant_id=? AND action='emailpostfach.sync'
                """,
                (tenant_id,),
            ).fetchone()
        return {
            "tool": "emailpostfach",
            "status": "ok",
            "metrics": {
                "unread_count": int(unread_row["c"] if unread_row else 0),
                "follow_ups_due": int(follow_up_row["c"] if follow_up_row else 0),
            },
            "last_sync": str(last_sync_row["last_sync"] or "") if last_sync_row else "",
            "updated_at": self._now_iso(),
        }

    def create_draft(self, *, tenant_id: str, actor: str, message: dict[str, Any], use_llm: bool = False) -> dict[str, Any]:
        if use_llm and self._llm_draft_generator:
            draft = self._llm_draft_generator(message)
            draft["generator"] = "llm"
        else:
            draft = generate_reply_draft(message, read_only_default=True, external_api_enabled=False)
            draft["generator"] = "template"

        draft_id = uuid4().hex
        to_address = str(message.get("from") or message.get("sender") or "")
        with self._db() as con:
            con.execute(
                """
                INSERT INTO emailpostfach_drafts(
                    id, tenant_id, to_address, subject, body, triage_category,
                    status, confirm_required, created_by, updated_by, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    draft_id,
                    tenant_id,
                    to_address,
                    str(draft.get("subject") or ""),
                    str(draft.get("body") or ""),
                    str((draft.get("triage") or {}).get("category") or classify_message(message).category),
                    "draft",
                    1,
                    actor,
                    actor,
                    self._now_iso(),
                ),
            )
        return {"id": draft_id, **draft, "to": to_address}

    def edit_draft(self, *, tenant_id: str, actor: str, draft_id: str, subject: str, body: str) -> dict[str, Any]:
        with self._db() as con:
            row = con.execute(
                "SELECT id FROM emailpostfach_drafts WHERE id=? AND tenant_id=?", (draft_id, tenant_id)
            ).fetchone()
            if not row:
                raise KeyError("draft_not_found")
            con.execute(
                """
                UPDATE emailpostfach_drafts
                SET subject=?, body=?, updated_by=?, updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                (subject, body, actor, self._now_iso(), draft_id, tenant_id),
            )
            con.execute(
                """
                INSERT INTO emailpostfach_audit(ts, tenant_id, username, action, target, details)
                VALUES (?,?,?,?,?,?)
                """,
                (self._now_iso(), tenant_id, actor, "emailpostfach.draft.edit", draft_id, "subject/body updated"),
            )
        return {"id": draft_id, "status": "edited", "confirm_required": True}

    def send_draft(self, *, tenant_id: str, actor: str, draft_id: str, confirm: bool) -> dict[str, Any]:
        if not confirm:
            return {"status": "blocked", "error": "explicit_confirm_required", "confirm_required": True}

        with self._db() as con:
            row = con.execute(
                """
                SELECT id, to_address, subject, body
                FROM emailpostfach_drafts
                WHERE id=? AND tenant_id=?
                """,
                (draft_id, tenant_id),
            ).fetchone()
            if not row:
                raise KeyError("draft_not_found")
            result = self._smtp_provider.send(to=row["to_address"], subject=row["subject"], body=row["body"])
            con.execute(
                "UPDATE emailpostfach_drafts SET status='sent', updated_by=?, updated_at=? WHERE id=?",
                (actor, self._now_iso(), draft_id),
            )
            con.execute(
                """
                INSERT INTO emailpostfach_audit(ts, tenant_id, username, action, target, details)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    self._now_iso(),
                    tenant_id,
                    actor,
                    "emailpostfach.send",
                    draft_id,
                    f"provider={result.get('provider')} id={result.get('provider_message_id')}",
                ),
            )
        return {"status": "sent", "confirm_required": True, "send_result": result}
