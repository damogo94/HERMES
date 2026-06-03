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


def _cmd_scan(args: argparse.Namespace) -> None:
    try:
        from hermes.intelligence.scanner import Scanner
    except ImportError:
        print("Faltan dependencias. Instala con: pip install -e .")
        return

    print(f"Escaneando {args.limit} mercados activos en busca de arbitraje "
          f"(edge mín {args.min_edge*100:.1f}%)... puede tardar un momento.")
    scanner = Scanner(min_edge=args.min_edge)
    try:
        opps = scanner.scan_arbitrage(limit=args.limit)
    finally:
        scanner.close()

    print(_LINE)
    print(f" Oportunidades de arbitraje  ({len(opps)})")
    print(_LINE)
    if not opps:
        print(" Ninguna por encima del umbral. (Los arbs reales son raros y")
        print(" se cierran rápido; prueba a subir --limit o bajar --min-edge.)")
        return
    for o in opps:
        ay = o.detail.get("ask_yes")
        an = o.detail.get("ask_no")
        print(
            f" edge {o.edge_pct:5.2f}%  ~${o.est_profit_usd:>8,.2f}  "
            f"(YES {ay:.3f} + NO {an:.3f})  "
            f"{(o.question[:46] + '…') if len(o.question) > 47 else o.question}"
        )
    print(_LINE)
    print(" Solo DETECCIÓN (DRY-RUN). No se ha enviado ninguna orden.")
    print(" El edge teórico aún debe cubrir gas y posible slippage.")


def _cmd_backtest(args: argparse.Namespace) -> None:
    try:
        from hermes.backtest.data import load_series, pick_market
        from hermes.backtest.engine import Backtester
        from hermes.backtest.metrics import summarize
        from hermes.backtest.strategies import MeanReversion
        from hermes.data.clob import ClobReadClient
        from hermes.data.gamma import GammaClient
    except ImportError:
        print("Faltan dependencias. Instala con: pip install -e .")
        return

    gamma, clob = GammaClient(), ClobReadClient()
    try:
        market = pick_market(gamma, query=args.query)
        if market is None or not market.token_yes:
            print("No se encontró un mercado activo adecuado.")
            return
        series = load_series(clob, market.token_yes, interval=args.interval)
    finally:
        gamma.close()
        clob.close()

    print(_LINE)
    print(f" Backtest: {market.question[:52]}")
    print(_LINE)
    if len(series) < args.window + 2:
        print(f" Serie insuficiente ({len(series)} puntos). Prueba otro mercado/intervalo.")
        return

    strat = MeanReversion(
        window=args.window,
        band=args.band,
        take_profit=args.take_profit,
        stop_loss=args.stop_loss,
    )
    bt = Backtester(fee_bps=args.fee_bps, slippage=args.slippage, size=1.0)
    result = bt.run(series, strat)
    summary = summarize(result)

    print(f" estrategia ....... mean_reversion(window={args.window}, band={args.band})")
    print(f" datos ............ {len(series)} puntos, intervalo={args.interval}")
    print(f" precio ........... primero={series[0][1]:.3f}  último={series[-1][1]:.3f}")
    print(_LINE)
    for line in summary.as_lines():
        print(" " + line)
    print(_LINE)
    print(" Backtest mark-to-market sobre histórico de un mercado activo.")
    print(" Es simulación: no prueba edge garantizado ni se ha operado nada.")


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

    p_scan = sub.add_parser("scan", help="Detecta arbitraje YES/NO en mercados activos.")
    p_scan.add_argument("-n", "--limit", type=int, default=40, help="Mercados a escanear.")
    p_scan.add_argument(
        "-e", "--min-edge", type=float, default=0.01, dest="min_edge",
        help="Edge mínimo (fracción, p. ej. 0.01 = 1%%).",
    )

    p_bt = sub.add_parser("backtest", help="Backtest mark-to-market de una estrategia.")
    p_bt.add_argument("-q", "--query", default=None, help="Mercado a usar (texto). Si no, el primero activo.")
    p_bt.add_argument("--interval", default="1m", help="Ventana histórica (max,1m,1w,1d,6h,1h).")
    p_bt.add_argument("--window", type=int, default=24, help="Ventana SMA (nº de puntos).")
    p_bt.add_argument("--band", type=float, default=0.05, help="Banda de entrada (fracción bajo la SMA).")
    p_bt.add_argument("--take-profit", type=float, default=None, dest="take_profit", help="Take-profit (fracción).")
    p_bt.add_argument("--stop-loss", type=float, default=None, dest="stop_loss", help="Stop-loss (fracción).")
    p_bt.add_argument("--fee-bps", type=float, default=0.0, dest="fee_bps", help="Comisión por op (bps).")
    p_bt.add_argument("--slippage", type=float, default=0.0, help="Slippage por fill (fracción).")

    args = parser.parse_args()

    if args.command == "markets":
        _cmd_markets(args)
    elif args.command == "scan":
        _cmd_scan(args)
    elif args.command == "backtest":
        _cmd_backtest(args)
    else:  # status (por defecto)
        _cmd_status(args)


if __name__ == "__main__":
    main()
