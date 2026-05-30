from dataclasses import dataclass
from datetime import timedelta


WINDOW_DURATIONS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

PRICE_INDEXER_RANGE_BY_WINDOW = {
    "1h": "1d",
    "24h": "1d",
    "7d": "1m",
    "30d": "1m",
}


@dataclass(frozen=True)
class Window:
    label: str
    duration: timedelta
    price_indexer_range: str


def normalize_window(value: str) -> Window:
    label = value.strip()
    if label not in WINDOW_DURATIONS:
        supported = ", ".join(WINDOW_DURATIONS)
        raise ValueError(f"Unsupported window {value!r}. Supported windows: {supported}")
    return Window(
        label=label,
        duration=WINDOW_DURATIONS[label],
        price_indexer_range=PRICE_INDEXER_RANGE_BY_WINDOW[label],
    )


def all_windows() -> list[Window]:
    return [normalize_window(label) for label in WINDOW_DURATIONS]
