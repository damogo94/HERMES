"""CLI de HERMES. Fase 0: comando ``status``."""

from __future__ import annotations

import argparse

from hermes import __version__
from hermes.core.config import get_settings
from hermes.core.logging import setup_logging

_LINE = "=" * 60


def _print_status() -> None:
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
    print(" Fase 0: esqueleto. Sin lógica de datos ni de trading todavía.")


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    parser = argparse.ArgumentParser(
        prog="hermes",
        description=(
            "HERMES — herramienta de trading inteligente para mercados de predicción."
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=["status"],
        help="Comando a ejecutar (de momento: status).",
    )
    parser.parse_args()
    _print_status()


if __name__ == "__main__":
    main()
