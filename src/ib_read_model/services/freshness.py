from datetime import datetime, timezone


PriceStatus = str


def price_status(observed_at: datetime | None, *, now: datetime | None = None) -> PriceStatus:
    if observed_at is None:
        return "missing"

    current = now or datetime.now(timezone.utc)
    observed = observed_at
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)

    age_seconds = (current - observed).total_seconds()
    if age_seconds < 0:
        age_seconds = 0
    if age_seconds < 5 * 60:
        return "fresh"
    if age_seconds < 60 * 60:
        return "aging"
    if age_seconds < 24 * 60 * 60:
        return "stale"
    return "expired"
