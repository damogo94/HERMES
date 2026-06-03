"""
Cliente del Gamma API de Polymarket (metadatos de mercados) — SOLO LECTURA.

https://gamma-api.polymarket.com/markets

Devuelve objetos ``Market`` normalizados. No requiere autenticación.
"""

from __future__ import annotations

import requests

from hermes.core.constants import POLYMARKET_GAMMA
from hermes.core.logging import get_logger
from hermes.data.http import get_json, make_session
from hermes.data.models import Market

logger = get_logger("data.gamma")


class GammaClient:
    def __init__(self, base_url: str = POLYMARKET_GAMMA, session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or make_session()

    # ----- listados -----
    def list_markets(
        self,
        active: bool = True,
        closed: bool = False,
        limit: int = 100,
        order: str | None = None,
        ascending: bool = False,
    ) -> list[Market]:
        """Lista mercados con paginación por offset hasta ``limit`` resultados.

        ``order`` es opcional (p. ej. 'volumeNum'); se omite por defecto para
        no depender de un campo de ordenación que la API podría rechazar.
        """
        out: list[Market] = []
        offset = 0
        page = min(limit, 100)
        while len(out) < limit:
            params: dict = {
                "active": str(active).lower(),
                "closed": str(closed).lower(),
                "limit": page,
                "offset": offset,
            }
            if order:
                params["order"] = order
                params["ascending"] = str(ascending).lower()
            data = get_json(self.session, f"{self.base_url}/markets", params=params)
            rows = data if isinstance(data, list) else data.get("data", [])
            if not rows:
                break
            out.extend(Market.from_gamma(m) for m in rows)
            if len(rows) < page:
                break
            offset += page
        return out[:limit]

    def get_market(self, market_id: str) -> Market | None:
        try:
            data = get_json(self.session, f"{self.base_url}/markets/{market_id}")
        except requests.HTTPError as e:
            logger.warning("get_market(%s) falló: %s", market_id, e)
            return None
        if isinstance(data, list):
            data = data[0] if data else None
        return Market.from_gamma(data) if data else None

    def get_market_by_slug(self, slug: str) -> Market | None:
        data = get_json(self.session, f"{self.base_url}/markets", params={"slug": slug})
        rows = data if isinstance(data, list) else data.get("data", [])
        return Market.from_gamma(rows[0]) if rows else None

    def market_by_clob_token(self, token_id: str) -> Market | None:
        """Resuelve el mercado al que pertenece un clobTokenId."""
        for closed_flag in ("false", "true"):
            data = get_json(
                self.session,
                f"{self.base_url}/markets",
                params={"clob_token_ids": token_id, "closed": closed_flag, "limit": 1},
            )
            rows = data if isinstance(data, list) else data.get("data", [])
            if rows:
                return Market.from_gamma(rows[0])
        return None

    def search_markets(self, query: str, limit: int = 20, scan: int = 500) -> list[Market]:
        """
        Búsqueda por subcadena en la pregunta del mercado.

        Gamma no expone una búsqueda de texto fiable, así que traemos los
        mercados activos más voluminosos y filtramos del lado del cliente.
        """
        q = query.strip().lower()
        if not q:
            return []
        universe = self.list_markets(active=True, closed=False, limit=scan)
        hits = [m for m in universe if q in m.question.lower()]
        return hits[:limit]

    def close(self) -> None:
        self.session.close()
