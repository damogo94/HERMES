"""
Gestión de riesgo (Fase 4).

Topes duros (por trade / hora / total), control de precio y kill-switch.
TODA orden pasa por el RiskManager ANTES de la ejecución.
"""

from hermes.risk.manager import RiskDecision, RiskManager

__all__ = ["RiskManager", "RiskDecision"]
