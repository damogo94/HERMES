"""Modelos de orden compartidos entre estrategia, riesgo y ejecución."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


# Estados posibles de una orden tras pasar por el Executor.
STATUS_DRY_RUN = "dry_run"     # simulada (DRY_RUN): construida y registrada, NO enviada
STATUS_REJECTED = "rejected"   # bloqueada por el gestor de riesgo
STATUS_BLOCKED = "blocked"     # intento live sin firma implementada (Fase 5)
STATUS_SENT = "sent"           # enviada de verdad (solo Fase 5+)


@dataclass(frozen=True)
class OrderIntent:
    """Lo que el sistema QUIERE hacer. Aún no es una orden ejecutada."""

    market_id: str
    token_id: str
    side: str            # "BUY" | "SELL"
    price: float         # precio límite (0-1)
    size_usd: float      # nocional en USDC
    reason: str = ""     # de qué señal/estrategia procede

    def to_dict(self) -> dict:
        return {
            "market_id": self.market_id,
            "token_id": self.token_id,
            "side": self.side,
            "price": self.price,
            "size_usd": self.size_usd,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Order:
    """Resultado de procesar un OrderIntent por el Executor."""

    intent: OrderIntent
    status: str
    reason: str
    dry_run: bool
    ts: float = field(default_factory=time.time)

    @property
    def executed(self) -> bool:
        """¿Se envió dinero de verdad? (solo STATUS_SENT)."""
        return self.status == STATUS_SENT

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "status": self.status,
            "reason": self.reason,
            "dry_run": self.dry_run,
            "intent": self.intent.to_dict(),
        }
