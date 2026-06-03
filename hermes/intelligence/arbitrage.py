"""
Detector de arbitraje binario YES/NO.

En Polymarket, YES y NO de un mismo mercado son complementarios: 1 YES + 1 NO
siempre valen $1 al resolver (y se pueden fusionar de vuelta a $1 de colateral
con mergePositions). Por tanto, si puedes COMPRAR ambos lados por menos de $1
en total, el beneficio está (teóricamente) garantizado:

    edge = 1 - (mejor_ask_YES + mejor_ask_NO)

Si edge > umbral (que debe cubrir gas + slippage), es una oportunidad.

⚠️  Es detección, no garantía: captarla requiere ejecución (fase 5), pagar gas
y que nadie se adelante. Aquí solo calculamos; no se envía nada.
"""

from __future__ import annotations

from hermes.data.models import Market, OrderBook, OrderLevel
from hermes.intelligence.models import Opportunity


def _best_ask_level(book: OrderBook) -> OrderLevel | None:
    """Nivel de ask con el precio más bajo (el que pagarías al comprar)."""
    if not book.asks:
        return None
    return min(book.asks, key=lambda lvl: lvl.price)


class ArbitrageDetector:
    def __init__(self, min_edge: float = 0.01):
        # Umbral mínimo de edge (fracción) para marcar una oportunidad.
        # Por defecto 0.01 (1c por par) para cubrir gas/slippage.
        self.min_edge = min_edge

    def evaluate(
        self,
        market: Market,
        book_yes: OrderBook,
        book_no: OrderBook,
    ) -> Opportunity | None:
        ask_yes = _best_ask_level(book_yes)
        ask_no = _best_ask_level(book_no)
        if ask_yes is None or ask_no is None:
            return None

        cost = ask_yes.price + ask_no.price
        edge = 1.0 - cost
        if edge < self.min_edge:
            return None

        # Tamaño aprovechable = mínimo de los tamaños disponibles al mejor ask
        # (en "shares"; cada par devuelve $1 al fusionar/resolver).
        max_pairs = min(ask_yes.size, ask_no.size)
        capital = cost * max_pairs
        profit = edge * max_pairs

        return Opportunity(
            kind="arb_binary",
            market_id=market.id,
            question=market.question,
            edge=edge,
            est_profit_usd=profit,
            capital_usd=capital,
            detail={
                "ask_yes": ask_yes.price,
                "ask_no": ask_no.price,
                "cost": cost,
                "max_pairs": max_pairs,
                "token_yes": market.token_yes,
                "token_no": market.token_no,
                "neg_risk": market.neg_risk,
            },
        )
