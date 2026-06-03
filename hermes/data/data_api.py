"""
Cliente de la Data API de Polymarket (+ leaderboard) — SOLO LECTURA.

- data-api.polymarket.com: trades (global y por wallet), posiciones, valor.
- lb-api.polymarket.com: leaderboard de carteras por beneficio.

Devuelve dicts crudos (las claves de la API ya son claras). No autentica.
"""

from __future__ import annotations

import requests

from hermes.core.constants import POLYMARKET_DATA_API, POLYMARKET_LB_API
from hermes.core.logging import get_logger
from hermes.data.http import get_json, make_session

logger = get_logger("data.data_api")


class DataAPIClient:
    def __init__(
        self,
        base_url: str = POLYMARKET_DATA_API,
        lb_url: str = POLYMARKET_LB_API,
        session: requests.Session | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.lb_url = lb_url.rstrip("/")
        self.session = session or make_session()

    def leaderboard(self, window: str = "all", limit: int = 20) -> list[dict]:
        """Top carteras por BENEFICIO. window: all (confirmado), quizá 1d/7d/30d.

        Devuelve [{proxyWallet, amount, name, pseudonym, ...}, ...].
        """
        data = get_json(
            self.session,
            f"{self.lb_url}/profit",
            params={"window": window, "limit": limit},
        )
        return data if isinstance(data, list) else data.get("data", [])

    def recent_trades(self, limit: int = 100) -> list[dict]:
        """Trades globales recientes (cualquier cartera)."""
        data = get_json(self.session, f"{self.base_url}/trades", params={"limit": limit})
        return data if isinstance(data, list) else data.get("data", [])

    def user_trades(self, wallet: str, limit: int = 100) -> list[dict]:
        """Trades de una cartera concreta (con price, asset, outcomeIndex, timestamp)."""
        data = get_json(
            self.session,
            f"{self.base_url}/trades",
            params={"user": wallet, "limit": limit},
        )
        return data if isinstance(data, list) else data.get("data", [])

    def user_positions(self, wallet: str, limit: int = 100) -> list[dict]:
        """Posiciones de una cartera (incluye realizedPnl, percentPnl, curPrice)."""
        data = get_json(
            self.session,
            f"{self.base_url}/positions",
            params={"user": wallet, "limit": limit},
        )
        return data if isinstance(data, list) else data.get("data", [])

    def user_value(self, wallet: str) -> float | None:
        data = get_json(self.session, f"{self.base_url}/value", params={"user": wallet})
        try:
            if isinstance(data, list) and data:
                return float(data[0].get("value"))
            if isinstance(data, dict):
                return float(data.get("value"))
        except (TypeError, ValueError):
            return None
        return None

    def close(self) -> None:
        self.session.close()
