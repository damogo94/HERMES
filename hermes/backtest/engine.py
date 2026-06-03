"""
Motor de backtesting — replay event-driven, mark-to-market.

Reproduce una serie temporal de precios de un token y deja que una estrategia
emita intenciones BUY/SELL. Calcula P&L marcando a mercado (entras a un precio,
sales a otro precio posterior), SIN depender de la resolución del mercado.

Esto refleja el dato realmente disponible: Polymarket sirve histórico de precios
para mercados ABIERTOS (no para los ya resueltos). Una posición abierta al final
de la serie se cierra al último precio (mark-to-market).

Long-only por simplicidad (comprar un lado y venderlo después). Es simulación:
no firma ni envía nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClosedTrade:
    entry_t: int
    exit_t: int
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    ret: float          # retorno sobre el precio de entrada
    forced_exit: bool   # True si se cerró al final de la serie (mark-to-market)


@dataclass
class BacktestResult:
    token_id: str
    n_ticks: int
    trades: list[ClosedTrade] = field(default_factory=list)
    final_price: float | None = None

    @property
    def equity_curve(self) -> list[float]:
        """P&L acumulado tras cada trade cerrado."""
        eq, acc = [], 0.0
        for t in self.trades:
            acc += t.pnl
            eq.append(acc)
        return eq

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)


class Backtester:
    def __init__(self, fee_bps: float = 0.0, slippage: float = 0.0, size: float = 1.0):
        """
        fee_bps  — comisión por operación en puntos básicos del nocional (0 = sin fee).
        slippage — fracción de deslizamiento aplicada al precio de cada fill.
        size     — tamaño fijo (en "shares") por operación.
        """
        self.fee_bps = fee_bps
        self.slippage = slippage
        self.size = size

    def _fee(self, price: float) -> float:
        return abs(price) * self.size * (self.fee_bps / 10_000.0)

    def run(self, series: list[tuple[int, float]], strategy) -> BacktestResult:
        strategy.reset()
        trades: list[ClosedTrade] = []
        pos: dict | None = None  # {"t": int, "price": float}

        for t, price in series:
            action = strategy.on_tick(t, price, in_position=pos is not None)

            if action == "BUY" and pos is None:
                eff = price * (1.0 + self.slippage)
                pos = {"t": t, "price": eff, "fee": self._fee(eff)}

            elif action == "SELL" and pos is not None:
                eff = price * (1.0 - self.slippage)
                trades.append(self._close(pos, t, eff, forced=False))
                pos = None

        # Cierre forzoso al final de la serie (mark-to-market).
        if pos is not None and series:
            last_t, last_p = series[-1]
            eff = last_p * (1.0 - self.slippage)
            trades.append(self._close(pos, last_t, eff, forced=True))

        return BacktestResult(
            token_id=getattr(strategy, "token_id", ""),
            n_ticks=len(series),
            trades=trades,
            final_price=(series[-1][1] if series else None),
        )

    def _close(self, pos: dict, exit_t: int, exit_price: float, forced: bool) -> ClosedTrade:
        fees = pos["fee"] + self._fee(exit_price)
        gross = (exit_price - pos["price"]) * self.size
        pnl = gross - fees
        ret = (pnl / (pos["price"] * self.size)) if pos["price"] > 0 else 0.0
        return ClosedTrade(
            entry_t=pos["t"],
            exit_t=exit_t,
            entry_price=pos["price"],
            exit_price=exit_price,
            size=self.size,
            pnl=pnl,
            ret=ret,
            forced_exit=forced,
        )
