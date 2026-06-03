"""
Modelos normalizados de la capa de datos.

Estos dataclasses desacoplan el resto de HERMES de la forma cruda del JSON
de cada API. Todo el parseo tolerante (strings JSON, campos ausentes) vive aquí.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def _parse_json_list(value: Any) -> list:
    """Acepta una lista ya parseada o un string JSON ('["a","b"]') y devuelve list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def _to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


# --------------------------------------------------------------------------- #
# Order book
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class OrderLevel:
    price: float
    size: float


@dataclass(frozen=True)
class OrderBook:
    token_id: str
    bids: list[OrderLevel] = field(default_factory=list)
    asks: list[OrderLevel] = field(default_factory=list)
    timestamp: int | None = None

    @property
    def best_bid(self) -> float | None:
        return max((lvl.price for lvl in self.bids), default=None)

    @property
    def best_ask(self) -> float | None:
        return min((lvl.price for lvl in self.asks), default=None)

    @property
    def mid(self) -> float | None:
        bb, ba = self.best_bid, self.best_ask
        if bb is None or ba is None:
            return None
        return (bb + ba) / 2.0

    @property
    def spread(self) -> float | None:
        bb, ba = self.best_bid, self.best_ask
        if bb is None or ba is None:
            return None
        return ba - bb

    @classmethod
    def from_clob(cls, token_id: str, payload: dict) -> "OrderBook":
        def levels(rows: Any) -> list[OrderLevel]:
            out: list[OrderLevel] = []
            for r in rows or []:
                if isinstance(r, dict):
                    p, s = _to_float(r.get("price")), _to_float(r.get("size"))
                else:  # [price, size]
                    try:
                        p, s = _to_float(r[0]), _to_float(r[1])
                    except (IndexError, TypeError):
                        p, s = None, None
                if p is not None and s is not None:
                    out.append(OrderLevel(p, s))
            return out

        ts = payload.get("timestamp")
        try:
            ts = int(ts) if ts is not None else None
        except (TypeError, ValueError):
            ts = None
        return cls(
            token_id=str(token_id),
            bids=levels(payload.get("bids")),
            asks=levels(payload.get("asks")),
            timestamp=ts,
        )


# --------------------------------------------------------------------------- #
# Market
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Market:
    id: str
    question: str
    slug: str = ""
    condition_id: str | None = None
    token_yes: str | None = None
    token_no: str | None = None
    outcomes: list[str] = field(default_factory=list)
    outcome_prices: list[float] = field(default_factory=list)
    active: bool = False
    closed: bool = False
    neg_risk: bool = False
    volume: float | None = None
    end_date: str | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def yes_price(self) -> float | None:
        return self.outcome_prices[0] if self.outcome_prices else None

    @property
    def no_price(self) -> float | None:
        if len(self.outcome_prices) >= 2:
            return self.outcome_prices[1]
        yp = self.yes_price
        return (1.0 - yp) if yp is not None else None

    @classmethod
    def from_gamma(cls, m: dict) -> "Market":
        tokens = [str(t) for t in _parse_json_list(m.get("clobTokenIds"))]
        prices = [p for p in (_to_float(x) for x in _parse_json_list(m.get("outcomePrices"))) if p is not None]
        outcomes = [str(o) for o in _parse_json_list(m.get("outcomes"))]
        return cls(
            id=str(m.get("id", "")),
            question=str(m.get("question", m.get("title", ""))),
            slug=str(m.get("slug", "")),
            condition_id=m.get("conditionId") or m.get("condition_id"),
            token_yes=tokens[0] if len(tokens) > 0 else None,
            token_no=tokens[1] if len(tokens) > 1 else None,
            outcomes=outcomes,
            outcome_prices=prices,
            active=_to_bool(m.get("active")),
            closed=_to_bool(m.get("closed")),
            neg_risk=_to_bool(m.get("negRisk") or m.get("neg_risk")),
            volume=_to_float(m.get("volumeNum", m.get("volume"))),
            end_date=m.get("endDate") or m.get("end_date_iso") or m.get("end_date"),
            raw=m,
        )


# --------------------------------------------------------------------------- #
# Trade (Data API / archivo histórico)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Trade:
    timestamp: int | None
    market: str | None
    asset_id: str | None
    side: str | None
    price: float | None
    size: float | None
    maker: str | None = None
    taker: str | None = None
    tx_hash: str | None = None

    @classmethod
    def from_data_api(cls, t: dict) -> "Trade":
        ts = t.get("timestamp")
        try:
            ts = int(ts) if ts is not None else None
        except (TypeError, ValueError):
            ts = None
        return cls(
            timestamp=ts,
            market=t.get("market") or t.get("conditionId"),
            asset_id=t.get("asset") or t.get("asset_id"),
            side=(str(t["side"]).upper() if t.get("side") else None),
            price=_to_float(t.get("price")),
            size=_to_float(t.get("size")),
            maker=t.get("maker") or t.get("makerAddress"),
            taker=t.get("taker") or t.get("takerAddress"),
            tx_hash=t.get("transactionHash") or t.get("tx_hash"),
        )
