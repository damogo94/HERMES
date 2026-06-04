# Bitácora de HERMES

Registro de qué construimos, qué decidimos y qué descubrimos. Lo más valioso del
proyecto no es el código: es la **disciplina de validación** que ha cazado tres
"edges" falsos antes de arriesgar un solo euro.

- **Repo:** https://github.com/damogo94/HERMES
- **Dashboard:** https://hermes-blush-seven.vercel.app
- **Estado:** infraestructura completa y segura · **ninguna estrategia validada todavía** · todo en *paper* (DRY-RUN)

---

## 1. Qué es HERMES

Una herramienta para **detectar y (eventualmente) operar oportunidades** en
mercados de predicción (Polymarket; Kalshi más adelante). Diseñada para ser
autónoma, pero **por fases y detrás de candados**: de fábrica es **imposible que
envíe una orden real**.

Dos piezas:
- **Paquete Python** (`hermes`): toda la lógica, vía CLI.
- **Dashboard estático** (`web/`): panel de solo lectura en Vercel, datos en vivo.

---

## 2. Cómo se construyó (por fases)

| Fase | Qué | Resultado |
|------|-----|-----------|
| **0** | Esqueleto: paquete, config con `DRY_RUN`, CLI `status`, constantes Polymarket verificadas | ✅ |
| **1** | Capa de datos (solo lectura): `GammaClient`, `ClobReadClient`, `ArchiveClient`, `DataAPIClient` | ✅ |
| **2** | Inteligencia: `ArbitrageDetector` (YES+NO < $1) + `Scanner` | ✅ |
| **3** | Backtest mark-to-market + **validación seria** (train/test, costes, baseline) | ✅ |
| **4** | Riesgo (topes + kill-switch) + Ejecución DRY-RUN (envío real **bloqueado**) | ✅ |
| **5** | Ejecución real (wallet/firma) | ⬜ bloqueada por diseño |
| **6** | Autonomía progresiva | ⬜ |

Cada fase se construyó, **se probó contra la API real** y se subió a GitHub
(auto-deploy del dashboard en cada push).

---

## 3. Arquitectura — el flujo de una decisión

```
1 DATOS  →  2 INTELIGENCIA  →  3 ESTRATEGIA  →  4 RIESGO  →  5 EJECUCIÓN
(lectura)   (señales)          (decide)         (topes,      (DRY-RUN: simula;
                                                 kill-switch)  LIVE: BLOQUEADO)
        ↑
   BACKTEST / VALIDACIÓN  (una estrategia no llega a producción sin pasar esto)
```

Separación estricta: el único módulo que (en Fase 5) tocaría la clave es
`hermes/execution/`, aislado a propósito.

### Garantía de seguridad
- `HERMES_DRY_RUN=true` por defecto → todo se simula y se registra, nada se envía.
- Aunque pongas `DRY_RUN=false`, la ruta de envío real **no está implementada** →
  devuelve `blocked`.
- `HERMES_KILL_SWITCH=true` o un fichero `data_store/STOP` detienen todo.
- Verificado en vivo: orden aprobada (dry-run), rechazada por tope, bloqueada con
  dry-run off, y kill-switch.

---

## 4. Comandos

```bash
hermes status                 # modo (DRY-RUN), venue, caps, wallet/LLM
hermes markets -q bitcoin     # mercados activos (Gamma)
hermes scan                   # arbitraje YES/NO en vivo
hermes backtest -q bitcoin    # backtest mark-to-market de una estrategia
hermes validate -s momentum --spread 0.02   # validación out-of-sample con costes
hermes paper --size 10        # pasa una orden por riesgo+ejecución (DRY-RUN)
hermes journal                # historial de órdenes simuladas
hermes whales                 # leaderboard de carteras por beneficio
hermes validate-whales        # whale-follow: edge vs baseline aleatorio
hermes whales-oos --source random   # validación OOS (split temporal, sin look-ahead)
hermes whales-net             # edge neto tras fricciones de copia
```

---

## 5. Estrategias probadas — y sus veredictos

> El patrón de los fallos es claro: **patrones de precio genéricos** y **"seguir
> a los que ganan"** no tienen edge real. Cada uno se cayó en una prueba distinta.

### 5.1 Reversión a la media y momentum (patrones de precio)
- **Primer backtest (un mercado, sin costes):** +76% / 92% win-rate → parecía oro.
- **Validación seria (multi-mercado, train/test, retorno compuesto, spread 2¢):**
  - mean_reversion: exceso sobre comprar-y-mantener **−57%**.
  - momentum: **−73%**.
- **Veredicto: SIN EDGE.** El "+76%" era artefacto de sumar %-retornos en tokens
  baratos; con costes y out-of-sample, pierden.

### 5.2 whale-follow (copiar carteras rentables)
Tesis: copiar a las carteras del leaderboard. P&L calculado vía **resolución del
mercado** (Gamma) — no necesita histórico de precios.

- **vs baseline aleatorio:** whales edge +32 pts (win 90% @ precio 0.58) vs +3.8
  del baseline → parecía señal real.
- **Walk-forward OOS (universo = leaderboard):** seleccionar carteras buenas en su
  1ª mitad → +25 pts en la 2ª, vs −6 las malas → "PERSISTE".
- **Edge neto (fricciones de copia):** aguantaba hasta ~27¢ de slippage.
- **Prueba final — universo ALEATORIO (`--source random`):** seleccionar carteras
  activas buenas-en-su-1ª-mitad → **−0.19 pts** en la 2ª (control −0.40). **≈0.**
- **Veredicto: NO VALIDADA.** El +25 del leaderboard era **survivorship**: el
  leaderboard se elige por beneficio de toda la historia, que solapa el test. Con
  un universo limpio, el rendimiento pasado **no predice** el futuro. Copiar el
  leaderboard **no tiene edge identificable**.

### Resumen
| Estrategia | Tesis | Veredicto |
|------------|-------|-----------|
| mean reversion | patrón de precio | sin edge (tras costes) |
| momentum | patrón de precio | sin edge (tras costes) |
| whale-follow | copiar ganadores | sin edge (survivorship) |

---

## 6. Lecciones / hallazgos clave

1. **Los datos importan más que el código.** Sondear cada fuente *antes* de
   construir evitó diseñar sobre supuestos falsos: el archivo de pmxt pesa ~350
   MB/hora; `prices-history` solo sirve mercados abiertos; Gamma resuelve varios
   `clob_token_ids` por llamada (batch); la Data API y el leaderboard `lb-api`.
2. **Casi todo "edge" es un espejismo.** Cada estrategia parecía ganar al
   principio y se caía en la prueba rigurosa (costes, out-of-sample, survivorship).
3. **La validación es el producto.** El mayor valor de HERMES es haber dicho "no"
   tres veces antes de arriesgar dinero.
4. **Honestidad por defecto.** Métrica robusta (retorno compuesto, edge =
   win_rate − precio) por encima de cifras infladas; caveats siempre visibles,
   también en el dashboard.

---

## 7. Stack técnico

- **Python 3.12** (venv local). Deps: `requests`, `httpx`, `pandas`, `polars`,
  `pyarrow`, `websockets`, `python-dotenv`.
- **Datos:** Gamma, CLOB, Data API, leaderboard (`lb-api`) y archivo de pmxt
  (Parquet) — todo público, solo lectura.
- **Dashboard:** HTML/JS estático (sin build), 3 pestañas (Panel · Whales ·
  Sistema), desplegado en **Vercel** con auto-deploy por Git.

---

## 8. Estado actual y próximos pasos

**Estado:** infraestructura completa y segura; **ninguna estrategia validada**;
todo en paper. Sin wallet ni ejecución real.

**Ideas con tesis que NO dependa de survivorship:**
1. **Arb cross-market** — el mismo evento en dos mercados/venues con precios
   distintos = beneficio *mecánico*, no estadístico. Requiere emparejar eventos
   (posible capa LLM) y añadir Kalshi.
2. **Nichos ineficientes** — mercados poco líquidos / no-cripto donde no llega el
   "smart money", en vez del crowd de cripto 5-min.

**Antes de la Fase 5 (dinero real):** una estrategia debe pasar la validación con
**universo limpio**; luego wallet desechable, límites mínimos y humano en el loop.
