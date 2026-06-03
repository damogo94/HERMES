"""
Validación seria de estrategias.

Cuatro defensas contra engañarse a uno mismo:

1. Multi-mercado: agrega sobre N mercados, no uno cherry-picked.
2. Costes reales: aplica fees + slippage por defecto.
3. Train/test temporal: optimiza/observa en la 1ª mitad, MIDE en la 2ª.
4. Baseline: compara contra "comprar y mantener YES" en el mismo tramo de test.

Regla honesta: si el retorno de test no supera al buy-and-hold (excess <= 0),
o si train >> test, NO hay edge demostrado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hermes.backtest.engine import Backtester
from hermes.backtest.metrics import summarize
from hermes.backtest.strategies import MeanReversion
from hermes.core.logging import get_logger
from hermes.data.clob import ClobReadClient
from hermes.data.gamma import GammaClient

logger = get_logger("backtest.validation")

Series = list[tuple[int, float]]


def split_series(series: Series, frac: float = 0.5) -> tuple[Series, Series]:
    """Parte la serie en (train, test) por tiempo. frac = proporción de train."""
    n = len(series)
    cut = max(1, int(n * frac))
    return series[:cut], series[cut:]


def buy_and_hold_return(series: Series) -> float:
    """Retorno de mantener YES desde el primer al último precio del tramo."""
    if len(series) < 2 or series[0][1] <= 0:
        return 0.0
    return (series[-1][1] - series[0][1]) / series[0][1]


@dataclass(frozen=True)
class MarketEval:
    question: str
    train_ret: float
    test_ret: float
    test_trades: int
    bh_test_ret: float

    @property
    def excess(self) -> float:
        return self.test_ret - self.bh_test_ret

    @property
    def beats_bh(self) -> bool:
        return self.test_ret > self.bh_test_ret


def evaluate_market(
    series: Series,
    window: int,
    band: float,
    fee_bps: float,
    slippage: float,
    split: float,
    question: str = "",
) -> MarketEval | None:
    train, test = split_series(series, split)
    if len(train) < window + 2 or len(test) < window + 2:
        return None

    def run(seg: Series) -> tuple[float, int]:
        strat = MeanReversion(window=window, band=band)
        res = Backtester(fee_bps=fee_bps, slippage=slippage).run(seg, strat)
        s = summarize(res)
        return s.total_ret, s.n_trades

    train_ret, _ = run(train)
    test_ret, test_trades = run(test)
    return MarketEval(
        question=question,
        train_ret=train_ret,
        test_ret=test_ret,
        test_trades=test_trades,
        bh_test_ret=buy_and_hold_return(test),
    )


@dataclass
class ValidationReport:
    evals: list[MarketEval] = field(default_factory=list)
    fee_bps: float = 0.0
    slippage: float = 0.0

    @property
    def n(self) -> int:
        return len(self.evals)

    @staticmethod
    def _mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    @property
    def mean_train_ret(self) -> float:
        return self._mean([e.train_ret for e in self.evals])

    @property
    def mean_test_ret(self) -> float:
        return self._mean([e.test_ret for e in self.evals])

    @property
    def mean_bh_test_ret(self) -> float:
        return self._mean([e.bh_test_ret for e in self.evals])

    @property
    def excess(self) -> float:
        return self.mean_test_ret - self.mean_bh_test_ret

    @property
    def beat_bh_rate(self) -> float:
        return self._mean([1.0 if e.beats_bh else 0.0 for e in self.evals])

    @property
    def profitable_rate(self) -> float:
        return self._mean([1.0 if e.test_ret > 0 else 0.0 for e in self.evals])

    @property
    def total_test_trades(self) -> int:
        return sum(e.test_trades for e in self.evals)

    def verdict(self) -> str:
        if self.n == 0:
            return "SIN DATOS suficientes para validar."
        if self.mean_test_ret <= 0 or self.excess <= 0:
            return "SIN EDGE out-of-sample (no supera a comprar-y-mantener tras costes)."
        # Overfit: train muy por encima de test.
        if self.mean_train_ret > 0 and self.mean_test_ret < 0.5 * self.mean_train_ret:
            return "PROBABLE OVERFIT (train >> test). Edge no fiable."
        return "Señal positiva out-of-sample. Requiere más datos antes de confiar."

    def as_lines(self) -> list[str]:
        return [
            f"mercados validados ... {self.n}",
            f"costes ............... fee={self.fee_bps}bps  slippage={self.slippage}",
            f"retorno medio TRAIN .. {self.mean_train_ret * 100:+.2f}%",
            f"retorno medio TEST ... {self.mean_test_ret * 100:+.2f}%",
            f"buy&hold medio TEST .. {self.mean_bh_test_ret * 100:+.2f}%",
            f"EXCESO sobre b&h ..... {self.excess * 100:+.2f}%   <- la cifra que importa",
            f"supera a b&h ......... {self.beat_bh_rate * 100:.0f}% de los mercados",
            f"mercados rentables ... {self.profitable_rate * 100:.0f}%",
            f"trades en test ....... {self.total_test_trades}",
        ]


def validate(
    strategy_params: dict,
    n_markets: int = 25,
    interval: str = "1m",
    min_points: int = 100,
    fee_bps: float = 0.0,
    slippage: float = 0.01,
    split: float = 0.5,
    gamma: GammaClient | None = None,
    clob: ClobReadClient | None = None,
) -> ValidationReport:
    from hermes.backtest.data import load_series

    g = gamma or GammaClient()
    c = clob or ClobReadClient()
    window = strategy_params.get("window", 24)
    band = strategy_params.get("band", 0.05)

    report = ValidationReport(fee_bps=fee_bps, slippage=slippage)
    try:
        # Escanea más mercados de los que validaremos (algunos no tendrán histórico).
        universe = g.list_markets(active=True, closed=False, limit=max(n_markets * 3, 60))
        for m in universe:
            if len(report.evals) >= n_markets:
                break
            if not m.token_yes:
                continue
            try:
                series = load_series(c, m.token_yes, interval=interval)
            except Exception as e:  # noqa: BLE001
                logger.debug("series falló %s: %s", m.id, e)
                continue
            if len(series) < min_points:
                continue
            ev = evaluate_market(
                series, window=window, band=band, fee_bps=fee_bps,
                slippage=slippage, split=split, question=m.question,
            )
            if ev is not None:
                report.evals.append(ev)
    finally:
        if gamma is None:
            g.close()
        if clob is None:
            c.close()
    return report
