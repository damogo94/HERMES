"""Modelos de la capa de inteligencia."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Opportunity:
    """Una oportunidad detectada (señal). NO es una orden ni una garantía.

    Captarla de verdad depende de la ejecución (fase 5), del gas y de que
    el mercado no se mueva antes (slippage / carrera).
    """

    kind: str                       # p. ej. "arb_binary"
    market_id: str
    question: str
    edge: float                     # beneficio por par de $1 (fracción, p. ej. 0.02 = 2%)
    est_profit_usd: float = 0.0     # beneficio estimado al tamaño aprovechable
    capital_usd: float = 0.0        # capital necesario para entrar
    detail: dict = field(default_factory=dict, repr=False)

    @property
    def edge_pct(self) -> float:
        return self.edge * 100.0
