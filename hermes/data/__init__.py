"""
Capa de datos (Fase 1) — SOLO LECTURA.

Ingesta de datos de mercado: histórico (archive.pmxt.dev) y en vivo
(Gamma / CLOB REST). No firma ni envía nada.

Clientes:
    GammaClient     — metadatos de mercados (gamma-api.polymarket.com)
    ClobReadClient  — order book / precios (clob.polymarket.com)
    ArchiveClient   — snapshots históricos en Parquet (pmxt)
"""

from hermes.data.archive import ArchiveClient
from hermes.data.clob import ClobReadClient
from hermes.data.data_api import DataAPIClient
from hermes.data.gamma import GammaClient
from hermes.data.kalshi import KalshiClient, KalshiMarket
from hermes.data.models import Market, OrderBook, OrderLevel, Trade

__all__ = [
    "GammaClient",
    "ClobReadClient",
    "ArchiveClient",
    "DataAPIClient",
    "KalshiClient",
    "KalshiMarket",
    "Market",
    "OrderBook",
    "OrderLevel",
    "Trade",
]
