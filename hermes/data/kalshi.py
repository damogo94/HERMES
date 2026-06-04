"""
Cliente de lectura de Kalshi — SOLO LECTURA, sin autenticación.

Usa el host público `api.elections.kalshi.com/trade-api/v2` (markets/events/
orderbook se leen sin token; el host `trading-api` exige auth y es solo para
operar). Normaliza el precio del lado YES a [0,1] como Polymarket.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

from hermes.core.logging import get_logger
from hermes.data.http import get_json, make_session

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"

logger = get_logger("data.kalshi")


def _to_dollars(v) -> float | None:
    """Kalshi da bid/ask/last en céntimos (1-99); normaliza a dólares [0,1]."""
    if v is None or v == "":
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v / 100.0 if v > 1 else v


@dataclass(frozen=True)
class KalshiMarket:
    ticker: str
    title: str
    event_ticker: str = ""
    yes_price: float | None = None     # [0,1], mid de bid/ask o último
    yes_bid: float | None = None
    yes_ask: float | None = None
    status: str = ""
    close_time: str | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, m: dict) -> "KalshiMarket":
        yb = _to_dollars(m.get("yes_bid"))
        ya = _to_dollars(m.get("yes_ask"))
        if yb is not None and ya is not None:
            yes = (yb + ya) / 2.0
        else:
            lpd = m.get("last_price_dollars")
            try:
                yes = float(lpd) if lpd not in (None, "") else _to_dollars(m.get("last_price"))
            except (TypeError, ValueError):
                yes = _to_dollars(m.get("last_price"))
        return cls(
            ticker=str(m.get("ticker", "")),
            title=str(m.get("title", "")),
            event_ticker=str(m.get("event_ticker", "")),
            yes_price=yes,
            yes_bid=yb,
            yes_ask=ya,
            status=str(m.get("status", "")),
            close_time=m.get("close_time"),
            raw=m,
        )


class KalshiClient:
    def __init__(self, base_url: str = KALSHI_BASE, session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or make_session()

    def list_events(self, limit: int = 600, status: str = "open") -> list[dict]:
        """Lista eventos (dicts crudos) paginando por cursor.

        Los eventos traen `category`, lo que permite filtrar el firehose de
        combos deportivos y quedarnos con elecciones/macro/mundo/etc.
        """
        out: list[dict] = []
        cursor = None
        while len(out) < limit:
            params = {"limit": min(200, limit - len(out)), "status": status}
            if cursor:
                params["cursor"] = cursor
            data = get_json(self.session, f"{self.base_url}/events", params=params)
            rows = data.get("events", []) if isinstance(data, dict) else []
            if not rows:
                break
            out.extend(rows)
            cursor = data.get("cursor") if isinstance(data, dict) else None
            if not cursor:
                break
        return out[:limit]

    def event_yes_price(self, event_ticker: str) -> tuple[float | None, str | None]:
        """Precio YES (y ticker) del primer mercado con precio de un evento."""
        try:
            data = get_json(
                self.session, f"{self.base_url}/markets",
                params={"event_ticker": event_ticker, "limit": 20},
            )
        except requests.RequestException:
            return None, None
        for m in (data.get("markets", []) if isinstance(data, dict) else []):
            km = KalshiMarket.from_api(m)
            if km.yes_price is not None:
                return km.yes_price, km.ticker
        return None, None

    def list_markets(self, limit: int = 400, status: str = "open") -> list[KalshiMarket]:
        """Lista mercados (paginando por cursor) hasta `limit`."""
        out: list[KalshiMarket] = []
        cursor = None
        while len(out) < limit:
            params = {"limit": min(1000, limit - len(out)), "status": status}
            if cursor:
                params["cursor"] = cursor
            data = get_json(self.session, f"{self.base_url}/markets", params=params)
            rows = data.get("markets", []) if isinstance(data, dict) else []
            if not rows:
                break
            out.extend(KalshiMarket.from_api(m) for m in rows)
            cursor = data.get("cursor") if isinstance(data, dict) else None
            if not cursor:
                break
        return out[:limit]

    def close(self) -> None:
        self.session.close()
