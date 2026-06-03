"""
Executor — ÚNICO punto por el que pasa una orden.

Encadena, en este orden estricto:
    1. Gestor de riesgo (topes, kill-switch). Si rechaza -> STATUS_REJECTED.
    2. Puerta DRY-RUN. Si DRY_RUN=true -> construye, registra y NO envía
       (STATUS_DRY_RUN).
    3. Ruta live -> deliberadamente NO implementada hasta la Fase 5 (firma con
       la clave privada). Devuelve STATUS_BLOCKED.

Resultado: en el estado actual del proyecto es IMPOSIBLE que HERMES envíe una
orden real. Cuando se implemente la Fase 5, el único cambio será la ruta live.
"""

from __future__ import annotations

from hermes.core.config import Settings, get_settings
from hermes.core.logging import get_logger
from hermes.execution.journal import Journal
from hermes.execution.models import (
    STATUS_BLOCKED,
    STATUS_DRY_RUN,
    STATUS_REJECTED,
    Order,
    OrderIntent,
)
from hermes.risk.manager import RiskManager

logger = get_logger("execution.executor")


class Executor:
    def __init__(
        self,
        settings: Settings | None = None,
        risk: RiskManager | None = None,
        journal: Journal | None = None,
    ):
        self.s = settings or get_settings()
        self.risk = risk or RiskManager(self.s)
        self.journal = journal or Journal(self.s)

    def submit(self, intent: OrderIntent) -> Order:
        # 1. Riesgo
        decision = self.risk.check(intent)
        if not decision.approved:
            return self._finish(Order(intent, STATUS_REJECTED, decision.reason, self.s.dry_run))

        # 2. Puerta DRY-RUN
        if self.s.dry_run:
            self.risk.register_fill(intent)
            return self._finish(
                Order(intent, STATUS_DRY_RUN, "DRY_RUN: orden simulada, NO enviada.", True)
            )

        # 3. Ruta live — bloqueada hasta la Fase 5 (firma/wallet)
        return self._finish(
            Order(
                intent,
                STATUS_BLOCKED,
                "Ejecución real no implementada (Fase 5). Mantén HERMES_DRY_RUN=true.",
                False,
            )
        )

    def _finish(self, order: Order) -> Order:
        logger.info(
            "orden=%s %s $%.2f @ %.3f | %s",
            order.status,
            order.intent.side,
            order.intent.size_usd,
            order.intent.price,
            order.reason,
        )
        self.journal.record(order.to_dict())
        return order
