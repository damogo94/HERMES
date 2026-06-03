"""
Estrategias de backtest (deterministas).

Una estrategia recibe cada tick (t, precio) y devuelve "BUY", "SELL" o None.
El motor gestiona la posición; la estrategia solo señala intención.
"""

from __future__ import annotations

from collections import deque


class Strategy:
    """Interfaz base. ``reset`` se llama al inicio de cada backtest."""

    name = "base"

    def reset(self) -> None:  # pragma: no cover - interfaz
        pass

    def on_tick(self, t: int, price: float, in_position: bool) -> str | None:  # pragma: no cover
        raise NotImplementedError


class MeanReversion(Strategy):
    """
    Reversión a la media sobre una media móvil simple (SMA).

    - Entra (BUY) si NO hay posición y el precio cae por debajo de
      ``sma * (1 - band)`` (sobre-vendido respecto a su media reciente).
    - Sale (SELL) si HAY posición y el precio vuelve a >= ``sma`` (revierte),
      o si el retorno desde la entrada alcanza ``take_profit``/``stop_loss``.

    Bounded a [0,1] como cualquier precio de mercado de predicción.
    """

    name = "mean_reversion"

    def __init__(
        self,
        window: int = 24,
        band: float = 0.05,
        take_profit: float | None = None,
        stop_loss: float | None = None,
    ):
        self.window = max(2, window)
        self.band = band
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self._prices: deque[float] = deque(maxlen=self.window)
        self._entry: float | None = None

    def reset(self) -> None:
        self._prices.clear()
        self._entry = None

    def _sma(self) -> float | None:
        if len(self._prices) < self.window:
            return None
        return sum(self._prices) / len(self._prices)

    def on_tick(self, t: int, price: float, in_position: bool) -> str | None:
        sma = self._sma()
        self._prices.append(price)  # incluir el tick actual para el siguiente cálculo

        if sma is None:
            return None  # aún calentando la ventana

        if not in_position:
            if price < sma * (1.0 - self.band):
                self._entry = price
                return "BUY"
            return None

        # En posición: decidir salida.
        if self._entry is not None and self._entry > 0:
            ret = (price - self._entry) / self._entry
            if self.take_profit is not None and ret >= self.take_profit:
                self._entry = None
                return "SELL"
            if self.stop_loss is not None and ret <= -abs(self.stop_loss):
                self._entry = None
                return "SELL"
        if price >= sma:
            self._entry = None
            return "SELL"
        return None
