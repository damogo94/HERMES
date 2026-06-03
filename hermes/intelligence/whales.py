"""
Whale-follow: ¿copiar carteras consistentemente rentables tiene edge?

Tesis: las carteras del top del leaderboard ganan dinero; ¿sus apuestas baten
las probabilidades IMPLÍCITAS del mercado (el precio al que entran)?

Métrica honesta y robusta:
    edge = win_rate − precio_medio_de_entrada
Si compran a 0.50 de media y aciertan el 60%, tienen skill (edge>0). Si aciertan
~50% (= su precio medio), solo asumen riesgo.

P&L sin price-history: cada trade trae su precio de entrada; el resultado (ganó
o no su lado) sale de la RESOLUCIÓN del mercado (Gamma, mercados cerrados).

Dos validaciones:
  1. whale_follow_report — edge de las top carteras vs baseline de carteras
     aleatorias. Rápido, pero la selección por beneficio pasado tiene sesgo.
  2. walk_forward (OOS) — selecciona carteras por su edge ANTES de un corte
     temporal T y mide SOLO sus trades POSTERIORES a T. Esto elimina el
     look-ahead: comprueba si la habilidad PERSISTE (skill) o se desvanece (suerte).

La resolución de mercados se hace por LOTES (Gamma acepta varios clob_token_ids
en una llamada con el parámetro repetido), para que sea viable.
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


# --------------------------------------------------------------------------- #
# Resolución de mercados (por lotes) → payoff por token
# --------------------------------------------------------------------------- #
def _payoff_for_token(m: Market, token: str) -> float | None:
    p = m.outcome_prices
    if len(p) >= 2 and max(p) >= 0.99 and min(p) <= 0.01:
        win_index = 0 if p[0] > p[1] else 1
        tok = str(token)
        idx = 0 if m.token_yes == tok else (1 if m.token_no == tok else None)
        if idx is not None:
            return 1.0 if idx == win_index else 0.0
    return None


def resolve_tokens(gamma: GammaClient, tokens, cache: dict, batch_size: int = 20) -> None:
    """Rellena `cache[token] = 1.0/0.0/None` para los tokens dados (por lotes).

    1.0 = ese token ganó, 0.0 = perdió, None = mercado no resuelto/desconocido.
    """
    need = [t for t in dict.fromkeys(tokens) if t and t not in cache]
    for i in range(0, len(need), batch_size):
        batch = need[i:i + batch_size]
        rows = []
        try:
            params = [("clob_token_ids", t) for t in batch]
            params += [("closed", "true"), ("limit", str(len(batch) * 2))]
            data = get_json(gamma.session, f"{gamma.base_url}/markets", params=params)
            rows = data if isinstance(data, list) else data.get("data", [])
        except Exception as e:  # noqa: BLE001
            logger.debug("batch resolución falló: %s", e)
        for row in rows:
            m = Market.from_gamma(row)
            for tok in (m.token_yes, m.token_no):
                if tok:
                    cache[tok] = _payoff_for_token(m, tok)
        for t in batch:           # los no devueltos = no resueltos
            cache.setdefault(t, None)


def _edge(records: list[tuple]) -> dict | None:
    """records: lista de (ts, price, payoff). Devuelve métricas o None."""
    if not records:
        return None
    n = len(records)
    wins = sum(1 for _, _, p in records if p > 0)
    avg_entry = sum(pr for _, pr, _ in records) / n
    win_rate = wins / n
    roi = sum((p - pr) / pr for _, pr, p in records) / n
    return {"n": n, "win_rate": win_rate, "avg_entry": avg_entry,
            "edge": win_rate - avg_entry, "mean_roi": roi}


def _records(trades: list[dict], cache: dict) -> list[tuple]:
    """Convierte trades crudos en (ts, price, payoff) para los ya resueltos."""
    recs: list[tuple] = []
    for t in trades:
        token = str(t.get("asset", ""))
        payoff = cache.get(token)
        if payoff is None:
            continue
        try:
            price = float(t.get("price"))
            ts = int(t.get("timestamp"))
        except (TypeError, ValueError):
            continue
        if 0.0 < price < 1.0:
            recs.append((ts, price, payoff))
    return recs


def evaluate_trades(trades: list[dict], gamma: GammaClient, cache: dict) -> dict | None:
    resolve_tokens(gamma, [str(t.get("asset", "")) for t in trades], cache)
    return _edge(_records(trades, cache))


# --------------------------------------------------------------------------- #
# Validación 1: top carteras vs baseline aleatorio (rápida, con sesgo)
# --------------------------------------------------------------------------- #
def _random_wallets(data: DataAPIClient, exclude: set, count: int) -> list[str]:
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
) -> dict:
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
    whale_eval = evaluate_trades(whale_trades, gamma, cache)

    base_trades: list[dict] = []
    for wallet in _random_wallets(data, exclude=whale_set, count=baseline_wallets):
        try:
            base_trades.extend(data.user_trades(wallet, limit=trades_per))
        except Exception as e:  # noqa: BLE001
            logger.debug("trades baseline de %s fallaron: %s", wallet, e)
    base_eval = evaluate_trades(base_trades, gamma, cache)

    return {"window": window, "whales": whales,
            "whale_eval": whale_eval, "base_eval": base_eval}


def verdict(report: dict) -> str:
    we, be = report.get("whale_eval"), report.get("base_eval")
    if not we:
        return "SIN DATOS: no se hallaron suficientes trades de whales resueltos."
    edge_w = we["edge"]
    edge_b = be["edge"] if be else 0.0
    if edge_w <= 0:
        return "SIN EDGE: las whales no baten las probabilidades implícitas."
    if be and edge_w > edge_b:
        return "SEÑAL POSITIVA: las whales baten al mercado y al baseline."
    return "Edge positivo pero NO superior al baseline. Débil; posible sesgo."


# --------------------------------------------------------------------------- #
# Validación 2: walk-forward OOS (la prueba honesta de persistencia)
# --------------------------------------------------------------------------- #
def _candidate_wallets(data: DataAPIClient, source: str, n: int) -> list[str]:
    """Universo de carteras candidatas.

    'leaderboard' = top por beneficio (ya-ganadores: confirma, no descubre).
    'random'      = carteras ACTIVAS aleatorias cosechadas de los trades globales
                    (sin filtrar por beneficio: prueba si el skill se IDENTIFICA
                    desde cero, no solo entre los top).
    """
    if source == "random":
        wallets: list[str] = []
        seen: set = set()
        for t in data.recent_trades(limit=min(max(n * 8, 500), 1000)):
            w = t.get("proxyWallet")
            if w and w not in seen:
                seen.add(w)
                wallets.append(w)
                if len(wallets) >= n:
                    break
        return wallets
    return [w["wallet"] for w in top_whales(data, window="all", limit=n)]


def walk_forward(
    data: DataAPIClient,
    gamma: GammaClient,
    universe: int = 40,
    trades_per: int = 150,
    split: float = 0.5,
    min_side: int = 5,
    window: str = "all",
    source: str = "leaderboard",
) -> dict:
    """Selecciona carteras por su edge ANTES del corte T; mide solo POST-T.

    Compara las 'seleccionadas' (edge pre-T > 0) contra las 'no seleccionadas'
    (edge pre-T <= 0) en su rendimiento posterior. Si las seleccionadas siguen
    ganando más, la habilidad PERSISTE (edge real). Si no, era sesgo/suerte.

    `source` define el universo: 'leaderboard' (confirma entre top) o 'random'
    (descubre skill entre carteras activas cualesquiera).
    """
    cache: dict = {}
    wallets = _candidate_wallets(data, source, universe)

    wallet_trades: dict[str, list] = {}
    all_tokens: list[str] = []
    for wallet in wallets:
        try:
            ts = data.user_trades(wallet, limit=trades_per)
        except Exception as e:  # noqa: BLE001
            logger.debug("trades de %s fallaron: %s", wallet, e)
            continue
        wallet_trades[wallet] = ts
        all_tokens += [str(t.get("asset", "")) for t in ts if t.get("asset")]

    resolve_tokens(gamma, all_tokens, cache)

    records: dict[str, list] = {}
    total_resolved = 0
    for wallet, trades in wallet_trades.items():
        recs = _records(trades, cache)
        if recs:
            records[wallet] = recs
            total_resolved += len(recs)

    if total_resolved < 30:
        return {"error": "pocos trades resueltos para un split fiable",
                "n_total": total_resolved}

    # Split POR CARTERA: la primera fracción temporal de cada wallet selecciona,
    # el resto mide. Así cualifica cualquier cartera con histórico suficiente,
    # sin depender de una fecha global (que excluía a las inactivas/recientes).
    selected: list[str] = []
    sel_after: list[tuple] = []
    non_after: list[tuple] = []
    qualified = 0
    for wallet, recs in records.items():
        recs.sort(key=lambda r: r[0])
        k = int(len(recs) * split)
        before, after = recs[:k], recs[k:]
        if len(before) < min_side or len(after) < min_side:
            continue
        qualified += 1
        pre = _edge(before)
        if pre and pre["edge"] > 0:
            selected.append(wallet)
            sel_after += after
        else:
            non_after += after

    return {
        "source": source,
        "qualified": qualified,
        "n_selected": len(selected),
        "sel": _edge(sel_after),
        "non": _edge(non_after),
        "sel_records": sel_after,   # para el modelo de edge neto
    }


# --------------------------------------------------------------------------- #
# Edge NETO: ¿cuánto del edge sobrevive a las fricciones de copia?
# --------------------------------------------------------------------------- #
def net_summary(records: list[tuple], slippage: float, gas_usd: float = 0.02,
                notional: float = 50.0) -> dict | None:
    """Aplica fricciones de copia a un conjunto de trades (post-corte).

    slippage = céntimos (en precio) que pagas PEOR que la whale (llegas tarde /
    mueves el precio). gas_usd = coste fijo por trade. notional = tamaño asumido
    por trade (amortiza el gas).

    net_edge = win_rate − precio_efectivo_medio  (métrica robusta; >0 = rentable).
    """
    n = len(records)
    if n == 0:
        return None
    gas_frac = gas_usd / notional if notional > 0 else 0.0
    wins = pos = 0
    sum_eff = sum_roi = 0.0
    for _, p, payoff in records:
        eff = min(p + slippage, 0.99)
        roi = (payoff - eff) / eff - gas_frac
        sum_eff += eff
        sum_roi += roi
        wins += 1 if payoff > 0 else 0
        pos += 1 if roi > 0 else 0
    return {
        "slippage": slippage,
        "n": n,
        "win_rate": wins / n,
        "avg_eff_entry": sum_eff / n,
        "net_edge": wins / n - sum_eff / n,
        "mean_roi": sum_roi / n,
        "pos_rate": pos / n,
    }


def breakeven_slippage(records: list[tuple], gas_usd: float = 0.02,
                       notional: float = 50.0, step: float = 0.0025,
                       cap: float = 0.30) -> float:
    """Slippage (en céntimos de precio) al que el net_edge cae a 0."""
    s = 0.0
    while s <= cap:
        ns = net_summary(records, s, gas_usd, notional)
        if not ns or ns["net_edge"] <= 0:
            return s
        s += step
    return cap  # el edge aguanta más allá del tope explorado


def oos_verdict(report: dict) -> str:
    if "error" in report:
        return f"SIN DATOS: {report['error']}."
    sel, non = report.get("sel"), report.get("non")
    if not sel:
        return "SIN DATOS: ninguna cartera seleccionada con suficientes trades post-corte."
    se = sel["edge"]
    ne = non["edge"] if non else 0.0
    if se <= 0:
        return "NO PERSISTE: el edge previo era sesgo de selección (suerte). Descartar."
    if non and se > ne:
        return "PERSISTE: las buenas-antes siguen ganando después → edge real, copiable."
    return "AMBIGUO: edge post-corte positivo pero no claramente superior. Más datos."
