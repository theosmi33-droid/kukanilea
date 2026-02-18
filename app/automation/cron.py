from __future__ import annotations

from datetime import datetime, timezone

CRON_FIELD_COUNT = 5
CRON_MAX_EXPRESSION_LENGTH = 120


def _parse_field(
    token: str, *, minimum: int, maximum: int, field_name: str
) -> int | None:
    value = str(token or "").strip()
    if value == "*":
        return None
    if not value.isdigit():
        raise ValueError(f"validation_error:cron_invalid_{field_name}")
    parsed = int(value)
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"validation_error:cron_out_of_range_{field_name}")
    return parsed


def parse_cron_expression(
    expression: str,
) -> tuple[int | None, int | None, int | None, int | None, int | None]:
    raw = str(expression or "").strip()
    if not raw:
        raise ValueError("validation_error:cron_empty")
    if len(raw) > CRON_MAX_EXPRESSION_LENGTH:
        raise ValueError("validation_error:cron_too_long")
    if any(ch not in "0123456789* \t" for ch in raw):
        raise ValueError("validation_error:cron_unsupported_syntax")
    parts = [p.strip() for p in raw.split() if p.strip()]
    if len(parts) != CRON_FIELD_COUNT:
        raise ValueError("validation_error:cron_field_count")
    minute = _parse_field(parts[0], minimum=0, maximum=59, field_name="minute")
    hour = _parse_field(parts[1], minimum=0, maximum=23, field_name="hour")
    day = _parse_field(parts[2], minimum=1, maximum=31, field_name="day")
    month = _parse_field(parts[3], minimum=1, maximum=12, field_name="month")
    # Sunday=0, Monday=1 ... Saturday=6
    weekday = _parse_field(parts[4], minimum=0, maximum=6, field_name="weekday")
    return minute, hour, day, month, weekday


def cron_match(expression: str, dt: datetime) -> bool:
    minute, hour, day, month, weekday = parse_cron_expression(expression)
    current = dt.replace(second=0, microsecond=0)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    current_weekday = (current.weekday() + 1) % 7
    return (
        (minute is None or minute == current.minute)
        and (hour is None or hour == current.hour)
        and (day is None or day == current.day)
        and (month is None or month == current.month)
        and (weekday is None or weekday == current_weekday)
    )


def cron_minute_ref(dt: datetime) -> str:
    current = dt.replace(second=0, microsecond=0)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    return current.strftime("%Y%m%d%H%M")
