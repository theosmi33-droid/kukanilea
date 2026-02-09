from __future__ import annotations

try:
    from kukanilea_weather_plugin import get_weather  # type: ignore
except Exception:  # pragma: no cover
    get_weather = None
