from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class EmailDraft:
    to: str
    subject: str
    body: str


class EmailProvider:
    name = "base"

    def send(self, draft: EmailDraft) -> Dict[str, str]:
        raise NotImplementedError


class DummyProvider(EmailProvider):
    name = "dummy"

    def send(self, draft: EmailDraft) -> Dict[str, str]:
        return {
            "status": "queued",
            "message": f"Dummy send: to={draft.to} subject={draft.subject}",
        }


class FutureGmailProvider(EmailProvider):
    name = "gmail"

    def send(self, draft: EmailDraft) -> Dict[str, str]:
        return {
            "status": "disabled",
            "message": "Gmail Provider ist ein Platzhalter (keine Credentials).",
        }
