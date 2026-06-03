"""
Cliente de lectura del CLOB de Polymarket — SOLO LECTURA.

Endpoints públicos de https://clob.polymarket.com (order book, precio, spread,
histórico de precios, mercados de muestreo). NO firma ni envía órdenes: la
ejecución vive aislada en hermes/execution/ (fase 5).
"""

from __future__ import annotations

import requests

from hermes.core.constants import POLYMARKET_CLOB_REST
from hermes.core.logging import get_logger
from hermes.data.http import get_json, make_session
from hermes.data.models import OrderBook

logger = get_logger("data.clob")


class ClobReadClient:
    def __init__(self, base_url: str = POLYMARKET_CLOB_REST, session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or make_session()

    def get_order_book(self, token_id: str) -> OrderBook:
        data = get_json(self.session, f"{self.base_url}/book", params={"token_id": token_id})
        return OrderBook.from_clob(token_id, data)

    def get_price(self, token_id: str, side: str) -> float | None:
        data = get_json(
            self.session,
            f"{self.base_url}/price",
            params={"token_id": token_id, "side": side.upper()},
        )
        try:
            return float(data.get("price")) if isinstance(data, dict) else None
        except (TypeError, ValueError):
            return None

    def get_spread(self, token_id: str) -> float | None:
        data = get_json(self.session, f"{self.base_url}/spread", params={"token_id": token_id})
        try:
            return float(data.get("spread")) if isinstance(data, dict) else None
        except (TypeError, ValueError):
            return None

    def get_last_trade_price(self, token_id: str) -> dict:
        data = get_json(
            self.session, f"{self.base_url}/last-trade-price", params={"token_id": token_id}
        )
        return data if isinstance(data, dict) else {}

    def get_prices_history(
        self,
        token_id: str,
        interval: str = "1h",
        fidelity: int = 60,
        start_ts: int | None = None,
        end_ts: int | None = None,
    ) -> list[dict]:
        """Histórico de precios: lista de {"t": unix, "p": precio}."""
        params: dict = {"market": token_id, "interval": interval, "fidelity": fidelity}
        if start_ts is not None:
            params["startTs"] = start_ts
        if end_ts is not None:
            params["endTs"] = end_ts
        data = get_json(self.session, f"{self.base_url}/prices-history", params=params)
        return data.get("history", []) if isinstance(data, dict) else []

    def iter_sampling_markets(self, max_markets: int = 500):
        """Itera mercados activos vía el endpoint paginado /sampling-markets."""
        cursor = None
        yielded = 0
        while yielded < max_markets:
            params = {}
            if cursor:
                params["next_cursor"] = cursor
            data = get_json(self.session, f"{self.base_url}/sampling-markets", params=params)
            rows = data.get("data", []) if isinstance(data, dict) else []
            if not rows:
                break
            for row in rows:
                yield row
                yielded += 1
                if yielded >= max_markets:
                    return
            cursor = data.get("next_cursor") if isinstance(data, dict) else None
            if not cursor or cursor == "LTE=":
                break

    def close(self) -> None:
        self.session.close()
