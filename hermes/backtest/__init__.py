"""
Backtesting / paper-trading (Fase 3).

Reproduce estrategias sobre histórico de precios para medir si tienen edge real
antes de arriesgar dinero. Mark-to-market (entrada/salida por precio), porque el
histórico solo está disponible para mercados abiertos.

Componentes:
    Backtester      — motor de replay event-driven
    BacktestResult  — trades cerrados + curva de equity
    Strategy        — interfaz; MeanReversion como primera estrategia
    summarize       — métricas agregadas (win rate, retorno, drawdown)
    load_series     — serie de precios de un token (CLOB prices-history)
"""

from hermes.backtest.data import load_series, pick_market
from hermes.backtest.engine import Backtester, BacktestResult, ClosedTrade
from hermes.backtest.metrics import Summary, summarize
from hermes.backtest.strategies import (
    MeanReversion,
    Momentum,
    Strategy,
    build_strategy,
    strategy_names,
)
from hermes.backtest.validation import (
    MarketEval,
    ValidationReport,
    buy_and_hold_return,
    split_series,
    validate,
)

__all__ = [
    "Backtester",
    "BacktestResult",
    "ClosedTrade",
    "Strategy",
    "MeanReversion",
    "Momentum",
    "build_strategy",
    "strategy_names",
    "summarize",
    "Summary",
    "load_series",
    "pick_market",
    "validate",
    "ValidationReport",
    "MarketEval",
    "split_series",
    "buy_and_hold_return",
]
