from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from flask import current_app


EventHandler = Callable[[dict[str, Any]], None]


class SharedServices:
    """Small in-process event + notification hub used by domain modules."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self.notifications: list[dict[str, Any]] = []

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        handlers = self._subscribers[str(event_name)]
        if handler not in handlers:
            handlers.append(handler)

    def publish(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        for handler in list(self._subscribers.get(str(event_name), [])):
            handler(dict(payload or {}))

    def notify(self, message: str, *, level: str = "info", data: dict[str, Any] | None = None) -> None:
        item = {"level": str(level), "message": str(message), "data": dict(data or {})}
        self.notifications.append(item)
        try:
            current_app.logger.info("notification[%s]: %s", item["level"], item["message"])
        except Exception:
            # No app context in some unit tests.
            pass


shared_services = SharedServices()
