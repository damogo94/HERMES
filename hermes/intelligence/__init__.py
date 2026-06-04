"""
Capa de inteligencia (Fase 2).

Detecta oportunidades y genera señales sobre la capa de datos. SOLO LECTURA +
cálculo: nunca firma ni envía órdenes. Si se activa el LLM, este solo puntúa
señales; no tiene autoridad para gastar.

Componentes:
    Opportunity        — una oportunidad detectada (señal)
    ArbitrageDetector  — arbitraje binario YES/NO (ask_yes + ask_no < $1)
    Scanner            — orquesta datos + detectores
"""

from hermes.intelligence.arbitrage import ArbitrageDetector
from hermes.intelligence.cross_market import CrossPair, find_cross_arb
from hermes.intelligence.models import Opportunity
from hermes.intelligence.scanner import Scanner
from hermes.intelligence.whales import (
    breakeven_slippage,
    net_summary,
    oos_verdict,
    top_whales,
    verdict,
    walk_forward,
    whale_follow_report,
)

__all__ = [
    "Opportunity",
    "ArbitrageDetector",
    "Scanner",
    "find_cross_arb",
    "CrossPair",
    "top_whales",
    "whale_follow_report",
    "verdict",
    "walk_forward",
    "oos_verdict",
    "net_summary",
    "breakeven_slippage",
]
