"""
Arb cross-market: el mismo evento en dos venues (Polymarket vs Kalshi) a precios
distintos = beneficio MECÁNICO (no estadístico) si ambos resuelven igual.

Esta capa hace EMPAREJAMIENTO de candidatos por similitud de título (Jaccard de
tokens). Es una HEURÍSTICA conservadora que produce *candidatos para revisión
humana*, no operaciones automáticas.

⚠️ Riesgo de resolución: dos mercados con títulos parecidos pueden resolver
distinto (fuentes, fechas de corte, criterios). Un emparejamiento erróneo NO es
arbitraje: es una pérdida garantizada. Siempre hay que verificar las reglas de
resolución de ambos lados a mano antes de operar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hermes.core.logging import get_logger
from hermes.data.gamma import GammaClient
from hermes.data.kalshi import KalshiClient

logger = get_logger("intelligence.cross_market")

_STOP = set(
    "will the a an of in on by to be is are at for and or with this that yes no "
    "before after than market markets day days price who what when which whether "
    "win wins won end ends his her its 2024 2025 2026".split()
)


def _tokens(title: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9 ]", " ", (title or "").lower())
    return {w for w in cleaned.split() if (len(w) >= 3 or w.isdigit()) and w not in _STOP}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


# Categorías de Kalshi con eventos comparables a Polymarket (excluye el firehose
# de combos deportivos y entretenimiento, que rara vez existen en Polymarket).
_GOOD_CATEGORIES = {
    "Elections", "Politics", "Financials", "Economics", "World",
    "Science and Technology", "Climate and Weather", "Companies", "Health", "Crypto",
}


@dataclass
class CrossPair:
    poly_question: str
    kalshi_title: str
    similarity: float
    poly_yes: float
    kalshi_yes: float
    kalshi_ticker: str
    llm_reason: str = ""   # justificación del juez LLM (si se usó)

    @property
    def gap(self) -> float:
        """Discrepancia de precio YES entre venues (≈ beneficio bruto por par)."""
        return abs(self.poly_yes - self.kalshi_yes)


_JUDGE_SYSTEM = (
    "Eres un verificador ESTRICTO de mercados de predicción. Te doy dos mercados: "
    "A (Polymarket) y B (Kalshi). Decide si se refieren EXACTAMENTE al mismo evento "
    "y resolverían con el MISMO resultado y reglas. Sé estricto: 'ganar' no es lo "
    "mismo que 'presentarse'; sujetos, umbrales o fechas distintos => false. Ante la "
    "duda, false. Responde SOLO JSON: {\"same\": true|false, \"reason\": \"<breve>\"}."
)


def judge_same(llm, poly_q: str, kalshi_t: str) -> tuple[bool, str]:
    """Pregunta al LLM si dos mercados son el mismo evento+resolución."""
    try:
        d = llm.chat_json(_JUDGE_SYSTEM, f"A (Polymarket): {poly_q}\nB (Kalshi): {kalshi_t}")
        return bool(d.get("same")), str(d.get("reason", ""))[:140]
    except Exception as e:  # noqa: BLE001
        logger.debug("juez LLM falló: %s", e)
        return False, "error LLM"


def find_cross_arb(
    gamma: GammaClient,
    kalshi: KalshiClient,
    poly_limit: int = 300,
    event_limit: int = 600,
    min_sim: float = 0.4,
    top_price: int = 25,
    llm_client=None,
    llm_top: int = 25,
) -> list[CrossPair]:
    """Empareja mercados Polymarket con EVENTOS de Kalshi (filtrados por categoría)
    y mide el gap de precio. El precio de Kalshi se consulta solo para los mejores
    candidatos, para acotar las llamadas a la API."""
    polys = [
        p for p in gamma.list_markets(active=True, closed=False, limit=poly_limit)
        if p.yes_price is not None and p.question
    ]
    events = kalshi.list_events(limit=event_limit, status="open")

    # Candidatos Kalshi: solo categorías comparables, título + subtítulo.
    cand: list[tuple[dict, str, set]] = []
    for e in events:
        if e.get("category", "") not in _GOOD_CATEGORIES:
            continue
        title = f"{e.get('title', '')} {e.get('sub_title', '') or ''}".strip()
        tok = _tokens(title)
        if tok:
            cand.append((e, title, tok))

    # Mejor evento para cada mercado Polymarket (por encima del umbral).
    matched: list[tuple[float, object, dict, str]] = []
    for p in polys:
        ptok = _tokens(p.question)
        if not ptok:
            continue
        best_s, best_e, best_t = 0.0, None, ""
        for e, title, tok in cand:
            s = _jaccard(ptok, tok)
            if s > best_s:
                best_s, best_e, best_t = s, e, title
        if best_e is not None and best_s >= min_sim:
            matched.append((best_s, p, best_e, best_t))

    matched.sort(reverse=True, key=lambda x: x[0])

    # Si hay LLM: juzga los candidatos (¿mismo evento+resolución?) y descarta los
    # falsos (p. ej. 'ganar' vs 'presentarse'). Si no, se mantiene la heurística.
    results: list[CrossPair] = []
    judged = 0
    for sim, p, e, title in matched:
        if len(results) >= top_price:
            break
        reason = ""
        if llm_client is not None:
            if judged >= llm_top:
                break
            judged += 1
            same, reason = judge_same(llm_client, p.question, title)
            if not same:
                continue
        ky, kt = kalshi.event_yes_price(e.get("event_ticker", ""))
        if ky is None:
            continue
        results.append(CrossPair(
            poly_question=p.question,
            kalshi_title=title,
            similarity=sim,
            poly_yes=p.yes_price,
            kalshi_yes=ky,
            kalshi_ticker=kt or e.get("event_ticker", ""),
            llm_reason=reason,
        ))
    results.sort(key=lambda c: c.gap, reverse=True)
    return results
