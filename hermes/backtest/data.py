"""
Carga de datos históricos para backtesting.

Fuente ligera: el endpoint público ``prices-history`` del CLOB, que sirve series
de precio para mercados ABIERTOS (no para los ya resueltos). Por eso el backtest
es mark-to-market sobre mercados activos.
"""

from __future__ import annotations

from hermes.core.logging import get_logger
from hermes.data.clob import ClobReadClient
from hermes.data.gamma import GammaClient
from hermes.data.models import Market

logger = get_logger("backtest.data")


def load_series(
    clob: ClobReadClient,
    token_id: str,
    interval: str = "1m",
    fidelity: int = 60,
) -> list[tuple[int, float]]:
    """
    Devuelve [(t_unix, precio), ...] ordenado por tiempo.

    interval: ventana de historia ('max','1m'=1 mes,'1w','1d','6h','1h').
    fidelity: minutos entre puntos (60 = horario).
    """
    raw = clob.get_prices_history(token_id, interval=interval, fidelity=fidelity)
    out: list[tuple[int, float]] = []
    for pt in raw:
        try:
            out.append((int(pt["t"]), float(pt["p"])))
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: x[0])
    return out


def pick_market(
    gamma: GammaClient,
    query: str | None = None,
    limit: int = 50,
) -> Market | None:
    """Elige un mercado activo (por texto si se da ``query``, si no el primero)."""
    if query:
        hits = gamma.search_markets(query, limit=1, scan=max(limit, 200))
        return hits[0] if hits else None
    markets = gamma.list_markets(active=True, closed=False, limit=limit)
    for m in markets:
        if m.token_yes:
            return m
    return None
