"""
Cliente HTTP compartido para la capa de datos (solo lectura).

Una ``requests.Session`` con reintentos/backoff para 429 y 5xx, timeouts por
defecto y un User-Agent identificable. Todas las llamadas son GET a APIs
públicas — esta capa nunca firma ni envía órdenes.
"""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 viene con requests; ruta de import tolerante por versión
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover
    from requests.packages.urllib3.util.retry import Retry  # type: ignore

DEFAULT_TIMEOUT = 15
USER_AGENT = "HERMES/0.0.1 (+https://github.com/damogo94/HERMES)"


def make_session(total_retries: int = 3, backoff: float = 0.5) -> requests.Session:
    """Crea una sesión con reintentos automáticos en 429/5xx."""
    session = requests.Session()
    retry = Retry(
        total=total_retries,
        connect=total_retries,
        read=total_retries,
        status=total_retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session


def get_json(
    session: requests.Session,
    url: str,
    params: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    """GET + parseo JSON. Lanza requests.HTTPError en respuestas de error."""
    resp = session.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()
