"""CLI de HERMES.

Comandos:
    status   — muestra configuración y modo (DRY-RUN).
    markets  — lista/busca mercados activos de Polymarket (capa de datos, fase 1).
"""

from __future__ import annotations

import argparse
import sys

from hermes import __version__
from hermes.core.config import get_settings
from hermes.core.logging import setup_logging

_LINE = "=" * 60


def _cmd_status(_args: argparse.Namespace) -> None:
    s = get_settings()
    print(_LINE)
    print(f" HERMES v{__version__}")
    print(_LINE)
    if s.dry_run:
        print(" MODO: DRY-RUN (paper) — no se envían órdenes reales.")
    else:
        print(" *** MODO: LIVE — ejecución real habilitada. ***")
        print(" *** Si no era tu intención: pon HERMES_DRY_RUN=true ***")
    print()
    print(f" venue ............ {s.venue}")
    print(
        f" caps (USDC) ...... trade={s.max_usd_per_trade}  "
        f"hora={s.max_usd_per_hour}  total={s.max_usd_total}"
    )
    print(f" slippage máx ..... {s.max_slippage}")
    print(f" wallet ........... {'configurada' if s.has_wallet else 'no configurada'}")
    print(f" LLM (señal) ...... {'configurado' if s.has_llm else 'no configurado'}")
    print(f" data dir ......... {s.data_dir}")
    print(_LINE)


def _cmd_markets(args: argparse.Namespace) -> None:
    # Import perezoso: solo necesita 'requests' cuando se usa este comando.
    try:
        from hermes.data.gamma import GammaClient
    except ImportError:
        print("Faltan dependencias de datos. Instala con: pip install -e .")
        return

    client = GammaClient()
    try:
        if args.query:
            markets = client.search_markets(args.query, limit=args.limit)
            header = f"Mercados que contienen '{args.query}'"
        else:
            markets = client.list_markets(active=True, closed=False, limit=args.limit)
            header = "Mercados activos"
    finally:
        client.close()

    print(_LINE)
    print(f" {header}  ({len(markets)})")
    print(_LINE)
    if not markets:
        print(" (sin resultados)")
        return
    for m in markets:
        yp = f"{m.yes_price:.2f}" if m.yes_price is not None else "  ? "
        vol = f"${m.volume:,.0f}" if m.volume is not None else "—"
        q = (m.question[:54] + "…") if len(m.question) > 55 else m.question
        print(f" YES {yp}  vol {vol:>12}  {q}")


def main() -> None:
    # Salida UTF-8 en consolas Windows (evita mojibake con acentos y «—»).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    settings = get_settings()
    setup_logging(settings.log_level)

    parser = argparse.ArgumentParser(
        prog="hermes",
        description="HERMES — herramienta de trading inteligente para mercados de predicción.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Muestra configuración y modo de ejecución.")

    p_markets = sub.add_parser("markets", help="Lista/busca mercados activos.")
    p_markets.add_argument("-q", "--query", default=None, help="Filtra por texto en la pregunta.")
    p_markets.add_argument("-n", "--limit", type=int, default=10, help="Máximo de resultados.")

    args = parser.parse_args()

    if args.command == "markets":
        _cmd_markets(args)
    else:  # status (por defecto)
        _cmd_status(args)


if __name__ == "__main__":
    main()
