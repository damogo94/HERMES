"""
Whale-follow: ¿copiar carteras consistentemente rentables tiene edge?

Tesis: las carteras del top del leaderboard ganan dinero; ¿sus apuestas baten
las probabilidades IMPLÍCITAS del mercado (el precio al que entran)?

Métrica honesta y robusta:
    edge = win_rate − precio_medio_de_entrada
Si compran a 0.50 de media y aciertan el 60%, tienen skill predictivo (edge>0).
Si aciertan ~50% (= su precio medio), solo asumen riesgo, no skill.

P&L sin price-history: cada trade trae su precio de entrada; el resultado (ganó
o no su lado) sale de la RESOLUCIÓN del mercado (Gamma, mercados cerrados). Así
medimos hold-to-resolution sin necesitar series históricas de precio.

Control de sesgo: comparamos contra un baseline de traders ALEATORIOS (trades
globales recientes) medido igual. Si las whales no superan al baseline, el
"sigue a los ganadores" no aporta.

CAVEAT: las whales se seleccionan por beneficio pasado, que solapa con estas
mismas resoluciones. No es un test puramente out-of-sample; es un primer read
robusto (edge vs odds implícitas y vs baseline), no una garantía de futuro.
"""

from __future__ import annotations

from hermes.core.logging import get_logger
from hermes.data.data_api import DataAPIClient
from hermes.data.gamma import GammaClient
from hermes.data.http import get_json
from hermes.data.models import Market

logger = get_logger("intelligence.whales")


def top_whales(data: DataAPIClient, window: str = "all", limit: int = 15) -> list[dict]:
    """Top carteras por beneficio, normalizadas a {wallet, name, profit}."""
    out: list[dict] = []
    for w in data.leaderboard(window=window, limit=limit):
        wallet = w.get("proxyWallet")
        if not wallet:
            continue
        out.append({
            "wallet": wallet,
            "name": w.get("name") or w.get("pseudonym") or wallet[:10],
            "profit": w.get("amount"),
        })
    return out


def _resolved_payoff(gamma: GammaClient, token_id: str, cache: dict) -> float | None:
    """1.0 si ese token (lado) ganó, 0.0 si perdió, None si no resuelto/desconocido."""
    if token_id in cache:
        return cache[token_id]
    payoff: float | None = None
    try:
        data = get_json(
            gamma.session,
            f"{gamma.base_url}/markets",
            params={"clob_token_ids": token_id, "closed": "true", "limit": 1},
        )
        rows = data if isinstance(data, list) else data.get("data", [])
        if rows:
            m: Market = Market.from_gamma(rows[0])
            p = m.outcome_prices
            if len(p) >= 2 and max(p) >= 0.99 and min(p) <= 0.01:
                win_index = 0 if p[0] > p[1] else 1
                tok = str(token_id)
                tok_index = 0 if m.token_yes == tok else (1 if m.token_no == tok else None)
                if tok_index is not None:
                    payoff = 1.0 if tok_index == win_index else 0.0
    except Exception as e:  # noqa: BLE001
        logger.debug("resolución falló token %s: %s", token_id, e)
    cache[token_id] = payoff
    return payoff


def evaluate_trades(
    trades: list[dict],
    gamma: GammaClient,
    cache: dict,
    max_lookups: int = 200,
) -> dict | None:
    """Evalúa una lista de trades sobre mercados ya resueltos. Devuelve métricas."""
    n = wins = 0
    sum_entry = sum_roi = 0.0
    lookups = 0
    for t in trades:
        token = str(t.get("asset", ""))
        raw_price = t.get("price")
        if not token or raw_price in (None, ""):
            continue
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            continue
        if not (0.0 < price < 1.0):
            continue
        if token not in cache:
            if lookups >= max_lookups:
                continue
            lookups += 1
        payoff = _resolved_payoff(gamma, token, cache)
        if payoff is None:
            continue
        n += 1
        wins += 1 if payoff > 0 else 0
        sum_entry += price
        sum_roi += (payoff - price) / price
    if n == 0:
        return None
    win_rate = wins / n
    avg_entry = sum_entry / n
    return {
        "n": n,
        "win_rate": win_rate,
        "avg_entry": avg_entry,
        "edge": win_rate - avg_entry,
        "mean_roi": sum_roi / n,
    }


def _random_wallets(data: DataAPIClient, exclude: set, count: int) -> list[str]:
    """Cosecha carteras 'normales' de los trades globales recientes.

    Nota: NO usamos los trades recientes directamente porque son de hace segundos
    y sus mercados aún no han resuelto. En cambio sacamos las carteras y luego
    pedimos SU historial (que sí abarca mercados ya resueltos).
    """
    wallets: list[str] = []
    seen: set = set()
    for t in data.recent_trades(limit=300):
        w = t.get("proxyWallet")
        if w and w not in seen and w not in exclude:
            seen.add(w)
            wallets.append(w)
            if len(wallets) >= count:
                break
    return wallets


def whale_follow_report(
    data: DataAPIClient,
    gamma: GammaClient,
    n_whales: int = 6,
    trades_per: int = 15,
    window: str = "all",
    baseline_wallets: int = 12,
    max_lookups: int = 250,
) -> dict:
    """Compara el edge de copiar whales vs un baseline de carteras aleatorias.

    Ambos lados se miden igual: historial de trades de cada cartera, sobre
    mercados YA RESUELTOS, edge = win_rate − precio_medio_de_entrada.
    """
    cache: dict = {}
    whales = top_whales(data, window=window, limit=n_whales)

    whale_trades: list[dict] = []
    whale_set = set()
    for w in whales:
        whale_set.add(w["wallet"])
        try:
            whale_trades.extend(data.user_trades(w["wallet"], limit=trades_per))
        except Exception as e:  # noqa: BLE001
            logger.debug("trades de %s fallaron: %s", w["wallet"], e)

    whale_eval = evaluate_trades(whale_trades, gamma, cache, max_lookups)

    base_trades: list[dict] = []
    for wallet in _random_wallets(data, exclude=whale_set, count=baseline_wallets):
        try:
            base_trades.extend(data.user_trades(wallet, limit=trades_per))
        except Exception as e:  # noqa: BLE001
            logger.debug("trades baseline de %s fallaron: %s", wallet, e)
    base_eval = evaluate_trades(base_trades, gamma, cache, max_lookups)

    return {
        "window": window,
        "whales": whales,
        "whale_eval": whale_eval,
        "base_eval": base_eval,
    }


def verdict(report: dict) -> str:
    we = report.get("whale_eval")
    be = report.get("base_eval")
    if not we:
        return "SIN DATOS: no se hallaron suficientes trades de whales en mercados resueltos."
    edge_w = we["edge"]
    edge_b = be["edge"] if be else 0.0
    if edge_w <= 0:
        return "SIN EDGE: las whales no baten las probabilidades implícitas del mercado."
    if be and edge_w > edge_b:
        return "SEÑAL POSITIVA: las whales baten al mercado y al baseline de traders típicos."
    return "Edge positivo pero NO superior al baseline. Débil; podría ser ruido/sesgo."
