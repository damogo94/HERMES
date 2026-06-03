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

## Dashboard (Vercel)

**En vivo:** https://hermes-blush-seven.vercel.app

`web/index.html` es un panel estático (sin servidor) que lee datos en vivo de
Polymarket desde el navegador (CORS abierto) y muestra mercados activos + un
escáner de arbitraje YES/NO. Es **solo lectura**: no envía órdenes. Se despliega
en Vercel sirviendo el directorio `web/` (ver `vercel.json`).

Redesplegar tras cambios:
`npx vercel deploy --prod --yes --scope damogo-s-projects` (o conecta el repo en
Vercel para deploy automático en cada push).

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
hermes scan                   # detecta arbitraje YES/NO en mercados activos
hermes scan -n 60 -e 0.005    # escanea 60 mercados, edge mín 0.5%
hermes backtest -q bitcoin    # backtest mark-to-market de una estrategia
hermes validate -m 25 -s momentum --spread 0.02   # validación out-of-sample con costes
hermes paper -q bitcoin --size 10  # pasa una orden por riesgo+ejecución (DRY-RUN)
hermes journal                # historial de órdenes simuladas
hermes whales                 # top carteras por beneficio (leaderboard)
hermes validate-whales        # valida la tesis whale-follow (edge vs baseline)
```

Todo es solo lectura/simulación; nada de esto necesita wallet ni envía órdenes.

## Estado

**Fase 4** — riesgo + ejecución en DRY-RUN:
- Datos: `GammaClient`, `ClobReadClient`, `ArchiveClient`.
- Inteligencia: `ArbitrageDetector` + `Scanner` (`hermes scan`).
- Backtest + validación: `Backtester`, `MeanReversion`, `validate` (train/test,
  costes, baseline buy&hold).
- **Riesgo**: `RiskManager` (topes por trade/hora/total + kill-switch).
- **Ejecución**: `Executor`, único punto por el que pasa una orden:
  `riesgo → DRY-RUN (simula, no envía) → ruta live BLOQUEADA hasta Fase 5`.
  Todo queda en un `journal` JSONL.

### Garantía de seguridad

En el estado actual es **imposible** que HERMES envíe una orden real: aunque
pongas `HERMES_DRY_RUN=false`, la ruta de envío está deliberadamente sin
implementar (Fase 5) y devuelve `blocked`. Además, `HERMES_KILL_SWITCH=true` o un
fichero `data_store/STOP` detienen todo.

> ⚠️ Estrategias de precio (`mean_reversion`, `momentum`): **sin edge** —
> no superan a comprar-y-mantener tras costes (validación compuesta, spread 2¢).
>
> ✅ **whale-follow**: primera señal **positiva** — las top carteras aciertan el
> 90% entrando a precio medio 0.58 (edge +32 pts) frente a +3.8 pts de traders
> aleatorios. Promete, pero la selección es por beneficio pasado (no OOS puro):
> falta confirmarlo con un **split temporal** (elegir whales con datos antiguos y
> medir solo sus trades posteriores) antes de confiar. HERMES sigue en paper.
