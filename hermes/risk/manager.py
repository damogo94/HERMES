"""
Gestor de riesgo — la puerta por la que pasa TODA orden antes de ejecutarse.

Comprueba cada ``OrderIntent`` contra los topes de la configuración y contra el
kill-switch. Si algo no cuadra, rechaza. Es deterministra y conservador: ante
la duda, NO.

Topes (config / .env):
    HERMES_MAX_USD_PER_TRADE   nocional máximo por operación
    HERMES_MAX_USD_PER_HOUR    nocional máximo acumulado en la última hora
    HERMES_MAX_USD_TOTAL       nocional máximo acumulado en la sesión
    HERMES_MAX_SLIPPAGE        (informativo; el control fino vive en ejecución)

Kill-switch: HERMES_KILL_SWITCH=true  o  la presencia del fichero data_dir/STOP.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from hermes.core.config import Settings, get_settings
from hermes.core.logging import get_logger
from hermes.execution.models import OrderIntent

logger = get_logger("risk.manager")

_HOUR_SECONDS = 3600.0


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str


class RiskManager:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self._stop_file = Path(self.s.data_dir) / "STOP"
        self._spent_total: float = 0.0
        self._recent: deque[tuple[float, float]] = deque()  # (ts, usd)

    # ----- estado -----
    def _hour_spent(self, now: float) -> float:
        while self._recent and (now - self._recent[0][0]) > _HOUR_SECONDS:
            self._recent.popleft()
        return sum(usd for _, usd in self._recent)

    def kill_switch_active(self) -> bool:
        return bool(self.s.kill_switch) or self._stop_file.exists()

    # ----- decisión -----
    def check(self, intent: OrderIntent) -> RiskDecision:
        if self.kill_switch_active():
            return RiskDecision(False, "KILL-SWITCH activo: toda operación detenida.")

        notional = intent.size_usd
        if notional is None or notional <= 0:
            return RiskDecision(False, "Nocional inválido (<= 0).")

        if not (0.0 < intent.price < 1.0):
            return RiskDecision(False, f"Precio fuera de rango (0,1): {intent.price}.")

        if notional > self.s.max_usd_per_trade:
            return RiskDecision(
                False,
                f"Supera tope por operación: {notional} > {self.s.max_usd_per_trade} USDC.",
            )

        now = time.time()
        hour = self._hour_spent(now)
        if hour + notional > self.s.max_usd_per_hour:
            return RiskDecision(
                False,
                f"Supera tope por hora: {hour:.2f}+{notional} > {self.s.max_usd_per_hour} USDC.",
            )

        if self._spent_total + notional > self.s.max_usd_total:
            return RiskDecision(
                False,
                f"Supera tope total: {self._spent_total:.2f}+{notional} > {self.s.max_usd_total} USDC.",
            )

        return RiskDecision(True, "OK")

    def register_fill(self, intent: OrderIntent) -> None:
        """Actualiza los contadores como si la orden se hubiera ejecutado.

        Se llama tras una orden aprobada (también en DRY-RUN) para que los topes
        por hora/total tengan efecto durante la sesión.
        """
        now = time.time()
        self._recent.append((now, intent.size_usd))
        self._spent_total += intent.size_usd
        self._hour_spent(now)  # poda la ventana
