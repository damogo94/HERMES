"""
Capa de ejecución (Fase 5) — ÚNICO módulo que toca la clave privada.

Firma y envía órdenes vía el SDK oficial de Polymarket. Respeta el flag
DRY_RUN: si está activo, construye y REGISTRA la orden pero NUNCA la
transmite. Aislada a propósito del resto del sistema.

Pendiente de implementar en la Fase 5. No requiere wallet hasta entonces.
"""
