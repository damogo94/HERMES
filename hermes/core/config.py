"""
Configuración central de HERMES.

Carga variables de entorno (.env) en un objeto ``Settings`` inmutable.

``dry_run`` es el INTERRUPTOR MAESTRO de seguridad: cuando es ``True``
(por defecto), HERMES nunca debe transmitir órdenes reales.

Los secretos (``private_key``, ``llm_api_key``) se marcan ``repr=False``
para que nunca aparezcan en logs ni en ``repr()``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv aún no instalado (p. ej. ejecutando el esqueleto sin
    # `pip install -e .`). Caemos a leer solo os.environ.
    pass


def _as_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _as_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # ---- Seguridad ----
    dry_run: bool = True
    venue: str = "polymarket"

    # ---- Límites de riesgo (USDC) — se aplican a partir de la fase 4 ----
    max_usd_per_trade: float = 10.0
    max_usd_per_hour: float = 50.0
    max_usd_total: float = 200.0
    max_slippage: float = 0.03

    # ---- Datos / runtime ----
    data_dir: Path = Path("./data_store")
    log_level: str = "INFO"
    polygon_rpc: str = "https://polygon-rpc.com"

    # ---- LLM (capa de señal; sin autoridad de gasto) ----
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = ""
    llm_api_key: str | None = field(default=None, repr=False)

    # ---- Ejecución (SOLO fase 5) ----
    private_key: str | None = field(default=None, repr=False)
    proxy_wallet: str | None = None

    @property
    def has_wallet(self) -> bool:
        return bool(self.private_key) and bool(self.proxy_wallet)

    @property
    def has_llm(self) -> bool:
        return bool(self.llm_api_key)

    def summary(self) -> str:
        """Resumen legible y SEGURO (sin secretos) del estado actual."""
        return (
            f"venue={self.venue} dry_run={self.dry_run} "
            f"caps[trade={self.max_usd_per_trade} hour={self.max_usd_per_hour} "
            f"total={self.max_usd_total} slip={self.max_slippage}] "
            f"wallet={'sí' if self.has_wallet else 'no'} "
            f"llm={'sí' if self.has_llm else 'no'}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración (cacheada) leída del entorno/.env."""
    return Settings(
        dry_run=_as_bool("HERMES_DRY_RUN", True),
        venue=os.getenv("HERMES_VENUE", "polymarket"),
        max_usd_per_trade=_as_float("HERMES_MAX_USD_PER_TRADE", 10.0),
        max_usd_per_hour=_as_float("HERMES_MAX_USD_PER_HOUR", 50.0),
        max_usd_total=_as_float("HERMES_MAX_USD_TOTAL", 200.0),
        max_slippage=_as_float("HERMES_MAX_SLIPPAGE", 0.03),
        data_dir=Path(os.getenv("HERMES_DATA_DIR", "./data_store")),
        log_level=os.getenv("HERMES_LOG_LEVEL", "INFO").upper(),
        polygon_rpc=os.getenv("HERMES_POLYGON_RPC", "https://polygon-rpc.com"),
        llm_base_url=os.getenv("HERMES_LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        llm_model=os.getenv("HERMES_LLM_MODEL", ""),
        llm_api_key=os.getenv("HERMES_LLM_API_KEY") or None,
        private_key=os.getenv("HERMES_PRIVATE_KEY") or None,
        proxy_wallet=os.getenv("HERMES_PROXY_WALLET") or None,
    )
