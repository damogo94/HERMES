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
        from hermes.backtest.strategies import build_strategy
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

    strat = build_strategy(args.strategy, window=args.window, band=args.band)
    bt = Backtester(
        fee_bps=args.fee_bps, slippage=args.slippage, spread=args.spread, size=1.0
    )
    result = bt.run(series, strat)
    summary = summarize(result)

    print(f" estrategia ....... {args.strategy}(window={args.window}, band={args.band})")
    print(f" costes ........... fee={args.fee_bps}bps slippage={args.slippage} spread={args.spread}")
    print(f" datos ............ {len(series)} puntos, intervalo={args.interval}")
    print(f" precio ........... primero={series[0][1]:.3f}  último={series[-1][1]:.3f}")
    print(_LINE)
    for line in summary.as_lines():
        print(" " + line)
    print(_LINE)
    print(" Backtest mark-to-market sobre histórico de un mercado activo.")
    print(" Es simulación: no prueba edge garantizado ni se ha operado nada.")


def _cmd_validate(args: argparse.Namespace) -> None:
    try:
        from hermes.backtest.validation import validate
    except ImportError:
        print("Faltan dependencias. Instala con: pip install -e .")
        return

    print(f"Validando {args.strategy} sobre ~{args.markets} mercados "
          f"(train/test {args.split:.0%}, spread={args.spread}, slippage={args.slippage})...")
    print("Puede tardar (una petición de histórico por mercado).")
    report = validate(
        strategy_params={"strategy": args.strategy, "window": args.window, "band": args.band},
        n_markets=args.markets,
        interval=args.interval,
        fee_bps=args.fee_bps,
        slippage=args.slippage,
        spread=args.spread,
        split=args.split,
    )
    print(_LINE)
    print(" VALIDACIÓN out-of-sample")
    print(_LINE)
    for line in report.as_lines():
        print(" " + line)
    print(_LINE)
    print(" VEREDICTO: " + report.verdict())
    print(_LINE)
    print(" Retornos COMPUESTOS y netos de spread. Lo único que vale es el EXCESO")
    print(" sobre buy&hold; y que train≈test (robusto, no sobreajustado).")


def _cmd_paper(args: argparse.Namespace) -> None:
    try:
        from hermes.backtest.data import pick_market
        from hermes.data.clob import ClobReadClient
        from hermes.data.gamma import GammaClient
        from hermes.execution.executor import Executor
        from hermes.execution.models import OrderIntent
    except ImportError:
        print("Faltan dependencias. Instala con: pip install -e .")
        return

    gamma, clob = GammaClient(), ClobReadClient()
    try:
        market = pick_market(gamma, query=args.query)
        if market is None or not market.token_yes:
            print("No se encontró un mercado activo adecuado.")
            return
        token = market.token_yes
        price = args.price
        if price is None:
            try:
                book = clob.get_order_book(token)
                price = book.best_ask if args.side == "buy" else book.best_bid
            except Exception:  # noqa: BLE001
                price = None
            if price is None:
                price = market.yes_price
    finally:
        gamma.close()
        clob.close()

    if price is None:
        print("No pude determinar el precio; pasa --price.")
        return

    intent = OrderIntent(
        market_id=market.id,
        token_id=token,
        side=args.side.upper(),
        price=float(price),
        size_usd=args.size,
        reason="paper (manual)",
    )
    order = Executor().submit(intent)

    label = {
        "dry_run": "SIMULADA (no enviada)",
        "rejected": "RECHAZADA por riesgo",
        "blocked": "BLOQUEADA (ejecución real no implementada)",
    }.get(order.status, order.status)

    print(_LINE)
    print(f" PAPER: {market.question[:50]}")
    print(_LINE)
    print(f" intent ... {intent.side} YES  ${intent.size_usd:.2f} @ {intent.price:.3f}")
    print(f" estado ... {order.status.upper()}  →  {label}")
    print(f" motivo ... {order.reason}")
    print(_LINE)
    print(" Registrado en el journal. No se ha enviado nada real.")


def _cmd_journal(args: argparse.Namespace) -> None:
    try:
        from hermes.execution.journal import Journal
    except ImportError:
        print("Faltan dependencias. Instala con: pip install -e .")
        return
    import datetime as _dt

    entries = Journal().tail(args.limit)
    print(_LINE)
    print(f" Journal — últimas {len(entries)} entradas")
    print(_LINE)
    if not entries:
        print(" (vacío)")
        return
    for e in entries:
        ts = e.get("ts")
        when = (
            _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
            if ts else "?"
        )
        it = e.get("intent", {})
        print(
            f" {when}  {e.get('status', '?'):8}  "
            f"{it.get('side', '?')} ${it.get('size_usd', 0):.2f} @ {it.get('price', 0):.3f}  "
            f"{e.get('reason', '')[:38]}"
        )


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
    p_bt.add_argument("-s", "--strategy", default="mean_reversion",
                      choices=["mean_reversion", "momentum"], help="Estrategia.")
    p_bt.add_argument("--interval", default="1m", help="Ventana histórica (max,1m,1w,1d,6h,1h).")
    p_bt.add_argument("--window", type=int, default=24, help="Ventana SMA (nº de puntos).")
    p_bt.add_argument("--band", type=float, default=0.05, help="Banda de entrada (fracción sobre/bajo la SMA).")
    p_bt.add_argument("--fee-bps", type=float, default=0.0, dest="fee_bps", help="Comisión por op (bps).")
    p_bt.add_argument("--slippage", type=float, default=0.0, help="Slippage por fill (fracción).")
    p_bt.add_argument("--spread", type=float, default=0.0, help="Coste de spread absoluto (ida+vuelta, p. ej. 0.02).")

    p_val = sub.add_parser("validate", help="Validación seria: multi-mercado, costes, train/test, baseline.")
    p_val.add_argument("-m", "--markets", type=int, default=25, help="Nº de mercados a validar.")
    p_val.add_argument("-s", "--strategy", default="mean_reversion",
                       choices=["mean_reversion", "momentum"], help="Estrategia.")
    p_val.add_argument("--interval", default="1m", help="Ventana histórica (max,1m,1w,1d,6h,1h).")
    p_val.add_argument("--window", type=int, default=24, help="Ventana SMA.")
    p_val.add_argument("--band", type=float, default=0.05, help="Banda de entrada.")
    p_val.add_argument("--fee-bps", type=float, default=0.0, dest="fee_bps", help="Comisión por op (bps).")
    p_val.add_argument("--slippage", type=float, default=0.0, help="Slippage por fill (fracción).")
    p_val.add_argument("--spread", type=float, default=0.02, help="Coste de spread absoluto (ida+vuelta).")
    p_val.add_argument("--split", type=float, default=0.5, help="Proporción train (resto = test).")

    p_paper = sub.add_parser("paper", help="Pasa un OrderIntent por riesgo+ejecución (DRY-RUN).")
    p_paper.add_argument("-q", "--query", default=None, help="Mercado (texto). Si no, el primero activo.")
    p_paper.add_argument("--side", choices=["buy", "sell"], default="buy", help="Lado.")
    p_paper.add_argument("--size", type=float, default=10.0, help="Nocional en USDC.")
    p_paper.add_argument("--price", type=float, default=None, help="Precio límite (si no, best ask/bid).")

    p_journal = sub.add_parser("journal", help="Muestra el journal de órdenes simuladas.")
    p_journal.add_argument("-n", "--limit", type=int, default=15, help="Entradas a mostrar.")

    args = parser.parse_args()

    if args.command == "markets":
        _cmd_markets(args)
    elif args.command == "scan":
        _cmd_scan(args)
    elif args.command == "backtest":
        _cmd_backtest(args)
    elif args.command == "validate":
        _cmd_validate(args)
    elif args.command == "paper":
        _cmd_paper(args)
    elif args.command == "journal":
        _cmd_journal(args)
    else:  # status (por defecto)
        _cmd_status(args)


if __name__ == "__main__":
    main()
