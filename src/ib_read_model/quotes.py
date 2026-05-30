from dataclasses import dataclass


SUPPORTED_QUOTES = ("USD", "MXN", "BTC", "USDC")
QUOTE_TYPES = {
    "USD": "fiat",
    "MXN": "fiat",
    "BTC": "crypto",
    "USDC": "stablecoin",
}


@dataclass(frozen=True)
class Quote:
    currency: str
    quote_type: str


def normalize_quote(value: str) -> Quote:
    currency = value.strip().upper()
    if currency not in QUOTE_TYPES:
        supported = ", ".join(SUPPORTED_QUOTES)
        raise ValueError(f"Unsupported quote currency {value!r}. Supported quotes: {supported}")
    return Quote(currency=currency, quote_type=QUOTE_TYPES[currency])


def parse_quotes(value: str | None) -> list[Quote]:
    if value is None or value.strip() == "":
        return [normalize_quote("USD")]
    return [normalize_quote(part) for part in value.split(",") if part.strip()]
