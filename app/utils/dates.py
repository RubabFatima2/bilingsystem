"""Billing-period helpers.

The engine meters quotas against a monthly window. The documented rule is
the calendar month: usage_events.created_at is compared against [first day
of month, first day of next month).

Timestamps are naive UTC to match the ORM ``datetime.utcnow`` defaults.
"""

from datetime import UTC, datetime, timedelta


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def month_bounds(
    reference: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Return (period_start, period_end) covering the calendar month of
    ``reference`` (default: now)."""
    ref = reference or _utcnow()
    # Deliberately naive UTC: usage_events.created_at is naive (see models),
    # and comparing aware vs naive datetimes raises.
    start = datetime(ref.year, ref.month, 1)  # noqa: DTZ001
    if ref.month == 12:
        end = datetime(ref.year + 1, 1, 1)  # noqa: DTZ001
    else:
        end = datetime(ref.year, ref.month + 1, 1)  # noqa: DTZ001
    return start, end


def last_n_days(n: int) -> tuple[datetime, datetime]:
    end = _utcnow()
    start = end - timedelta(days=n)
    return start, end
