"""
Escáner de oportunidades.

Orquesta la capa de datos (Gamma + CLOB) y aplica los detectores sobre los
mercados activos. SOLO LECTURA: no firma ni envía nada.
"""

from __future__ import annotations

import requests

from hermes.core.logging import get_logger
from hermes.data.clob import ClobReadClient
from hermes.data.gamma import GammaClient
from hermes.intelligence.arbitrage import ArbitrageDetector
from hermes.intelligence.models import Opportunity

logger = get_logger("intelligence.scanner")


class Scanner:
    def __init__(
        self,
        gamma: GammaClient | None = None,
        clob: ClobReadClient | None = None,
        min_edge: float = 0.01,
    ):
        self.gamma = gamma or GammaClient()
        self.clob = clob or ClobReadClient()
        self.arb = ArbitrageDetector(min_edge=min_edge)

    def scan_arbitrage(self, limit: int = 40) -> list[Opportunity]:
        """Busca arbitraje binario YES/NO en los mercados activos.

        Hace 2 peticiones de order book por mercado, así que con ``limit`` alto
        tarda. Devuelve oportunidades ordenadas por edge (mayor primero).
        """
        markets = self.gamma.list_markets(active=True, closed=False, limit=limit)
        opps: list[Opportunity] = []

        for m in markets:
            if not (m.token_yes and m.token_no):
                continue
            try:
                book_yes = self.clob.get_order_book(m.token_yes)
                book_no = self.clob.get_order_book(m.token_no)
            except requests.RequestException as e:
                logger.debug("order book falló para %s: %s", m.id, e)
                continue

            opp = self.arb.evaluate(m, book_yes, book_no)
            if opp is not None:
                opps.append(opp)

        opps.sort(key=lambda o: o.edge, reverse=True)
        return opps

    def close(self) -> None:
        self.gamma.close()
        self.clob.close()
