"""Métricas agregadas de un backtest."""

from __future__ import annotations

from dataclasses import dataclass

from hermes.backtest.engine import BacktestResult


@dataclass(frozen=True)
class Summary:
    n_trades: int
    wins: int
    win_rate: float
    total_pnl: float          # en unidades de precio * size (≈ USDC si size en shares)
    avg_ret: float            # retorno medio por trade
    total_ret: float          # SUMA de retornos por trade (referencia; sobreestima)
    compounded_ret: float     # retorno COMPUESTO reinvirtiendo (la cifra honesta)
    max_drawdown: float       # peor caída del equity acumulado
    best_ret: float
    worst_ret: float

    def as_lines(self) -> list[str]:
        return [
            f"trades ........... {self.n_trades}",
            f"win rate ......... {self.win_rate * 100:.1f}%  ({self.wins}/{self.n_trades})",
            f"retorno COMPUESTO  {self.compounded_ret * 100:+.2f}%   <- la cifra honesta",
            f"retorno medio .... {self.avg_ret * 100:+.2f}% / trade",
            f"suma de retornos . {self.total_ret * 100:+.2f}%  (referencia, sobreestima)",
            f"mejor / peor ..... {self.best_ret * 100:+.2f}% / {self.worst_ret * 100:+.2f}%",
            f"max drawdown ..... {self.max_drawdown:.4f}",
        ]


def _max_drawdown(equity: list[float]) -> float:
    peak = 0.0
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = max(max_dd, peak - v)
    return max_dd


def summarize(result: BacktestResult) -> Summary:
    trades = result.trades
    n = len(trades)
    if n == 0:
        return Summary(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    rets = [t.ret for t in trades]
    wins = sum(1 for t in trades if t.pnl > 0)

    # Retorno compuesto: reinvierte todo el capital en cada trade secuencial.
    compounded = 1.0
    for r in rets:
        compounded *= (1.0 + r)
    compounded -= 1.0

    return Summary(
        n_trades=n,
        wins=wins,
        win_rate=wins / n,
        total_pnl=result.total_pnl,
        avg_ret=sum(rets) / n,
        total_ret=sum(rets),
        compounded_ret=compounded,
        max_drawdown=_max_drawdown(result.equity_curve),
        best_ret=max(rets),
        worst_ret=min(rets),
    )
