# HERMES

Herramienta de trading **inteligente y (lo más) autónoma** para mercados de predicción
(Polymarket primero; Kalshi después). Su objetivo: **detectar buenas oportunidades y operarlas**,
combinando un bot autónomo y market-making.

> ⚠️ Software financiero. Puede perder dinero. Se construye **por fases** y arranca en
> **modo simulación (DRY-RUN)**: nada real se ejecuta hasta validar la estrategia.

## Principio de seguridad

`HERMES_DRY_RUN=true` es el **interruptor maestro** (por defecto `true`). Con DRY-RUN activo,
HERMES hace todo el ciclo (lee mercados, detecta oportunidades, decide y *construye* órdenes)
pero **nunca las transmite**. El único módulo que toca la clave privada es `hermes/execution/`,
y está aislado a propósito. No se necesita wallet hasta la fase 5.

## Arquitectura

```
hermes/
├─ core/          configuración (DRY_RUN), logging, constantes verificadas
├─ data/          ingesta de datos de mercado            [solo lectura]
├─ intelligence/  detección de oportunidades / señales   (LLM solo puntúa)
├─ strategy/      decide qué operar (reglas + señal LLM)
├─ risk/          topes duros, slippage, kill-switch
├─ execution/     firma y envía órdenes (respeta DRY_RUN) [única con la clave]
└─ backtest/      paper-trading sobre histórico
```

## Hoja de ruta (por fases, seguro primero)

| Fase | Qué | Riesgo |
|------|-----|--------|
| 0 | Esqueleto, config, CLI de estado | Cero |
| 1 | Capa de datos (histórico + vivo, solo lectura) | Cero |
| 2 | Inteligencia: detectores de oportunidad + señal LLM | Cero |
| 3 | Backtesting / paper sobre histórico (validar edge) | Cero |
| 4 | Gestión de riesgo + ejecución en DRY-RUN | Cero |
| 5 | Ejecución real: wallet desechable, caps, humano en el loop | Alto (controlado) |
| 6 | Autonomía progresiva (loop/scheduler) tras validación | Alto |

## Puesta en marcha

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env        # Windows: copy .env.example .env
hermes status               # o: python -m hermes
```

Comandos disponibles:

```bash
hermes status                 # modo (DRY-RUN), venue, caps, wallet/LLM
hermes markets                # lista mercados activos de Polymarket
hermes markets -q bitcoin -n 5  # busca por texto
```

Todo es solo lectura; nada de esto necesita wallet.

## Estado

**Fase 1** — capa de datos (solo lectura) implementada:
`GammaClient` (mercados), `ClobReadClient` (order book / precios / histórico) y
`ArchiveClient` (snapshots Parquet de pmxt). Aún sin lógica de inteligencia ni
de trading.
