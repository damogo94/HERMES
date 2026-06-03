"""
Cliente del archivo histórico de pmxt (datos públicos, solo lectura).

Snapshots horarios del order book de Polymarket en Parquet:
    polymarket_orderbook_YYYY-MM-DDTHH.parquet   (UTC)
descargables desde el bucket R2 de pmxt.

⚠️  Cada snapshot pesa ~300-400 MB. Descarga solo las horas que necesites.
Los ficheros son datos, no código: trátalos como input no confiable y mantén
pyarrow/polars actualizados.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import requests

from hermes.core.constants import (
    PMXT_ARCHIVE_DOWNLOAD_BASE,
    PMXT_ARCHIVE_FILE_TEMPLATE,
)
from hermes.core.logging import get_logger
from hermes.data.http import make_session

logger = get_logger("data.archive")


def _stamp(dt: datetime) -> str:
    """Convierte un datetime a 'YYYY-MM-DDTHH' en UTC (truncado a la hora)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H")


class ArchiveClient:
    def __init__(
        self,
        data_dir: Path | str = "./data_store",
        download_base: str = PMXT_ARCHIVE_DOWNLOAD_BASE,
        session: requests.Session | None = None,
    ):
        self.download_base = download_base.rstrip("/")
        self.dir = Path(data_dir) / "archive" / "polymarket"
        self.session = session or make_session()

    def filename_for(self, dt: datetime) -> str:
        return PMXT_ARCHIVE_FILE_TEMPLATE.format(stamp=_stamp(dt))

    def url_for(self, dt: datetime) -> str:
        return f"{self.download_base}/{self.filename_for(dt)}"

    def download_hour(self, dt: datetime, overwrite: bool = False) -> Path:
        """Descarga (en streaming) el snapshot de una hora. Devuelve la ruta local."""
        self.dir.mkdir(parents=True, exist_ok=True)
        dest = self.dir / self.filename_for(dt)
        if dest.exists() and not overwrite:
            logger.info("Ya descargado: %s", dest.name)
            return dest

        url = self.url_for(dt)
        logger.info("Descargando %s (~varios cientos de MB)...", url)
        tmp = dest.with_suffix(dest.suffix + ".part")
        with self.session.get(url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):  # 1 MB
                    if chunk:
                        fh.write(chunk)
        tmp.replace(dest)
        logger.info("Guardado: %s", dest)
        return dest

    def load_hour(self, dt: datetime, overwrite: bool = False):
        """
        Descarga si hace falta y devuelve un ``polars.DataFrame`` del snapshot.

        Import perezoso de polars para no exigir la dependencia al importar el
        módulo (p. ej. en fases sin datos).
        """
        try:
            import polars as pl
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "polars no está instalado. Instala las dependencias de datos: "
                "pip install -e ."
            ) from e
        path = self.download_hour(dt, overwrite=overwrite)
        return pl.read_parquet(path)

    def close(self) -> None:
        self.session.close()
