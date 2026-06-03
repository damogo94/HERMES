"""
Capa de ejecución (Fase 4: DRY-RUN; Fase 5: envío real).

Único módulo que (en la Fase 5) tocará la clave privada. Hoy opera solo en
DRY-RUN: el ``Executor`` construye y registra órdenes pero NUNCA las transmite,
y la ruta de envío real está deliberadamente bloqueada.

Para evitar imports circulares, importa los submódulos directamente:
    from hermes.execution.executor import Executor
    from hermes.execution.models import OrderIntent, Order
    from hermes.execution.journal import Journal
"""
