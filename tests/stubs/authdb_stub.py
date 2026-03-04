from __future__ import annotations


class _AuthDBStub:
    """Small in-memory AuthDB substitute for integration-contract tests."""

    def __init__(self, users=None):
        self._users = list(users or [])

    def count_users(self) -> int:
        return len(self._users)

    def upsert_user(self, username: str, password_hash: str, created_at: str) -> None:
        self._users.append(
            {
                "username": username,
                "password_hash": password_hash,
                "created_at": created_at,
            }
        )
