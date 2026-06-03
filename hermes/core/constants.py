"""
Constantes compartidas: endpoints oficiales y direcciones de contrato.

Las direcciones de Polymarket en Polygon están VERIFICADAS en PolygonScan.
NO las modifiques sin re-verificar: aprobar gasto a un contrato equivocado
equivale a ceder tus fondos.
"""

# ---- Endpoints oficiales de Polymarket ----
POLYMARKET_CLOB_REST = "https://clob.polymarket.com"
POLYMARKET_CLOB_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
POLYMARKET_GAMMA = "https://gamma-api.polymarket.com"
POLYMARKET_DATA_API = "https://data-api.polymarket.com"

# ---- Polygon ----
POLYGON_CHAIN_ID = 137

# ---- Direcciones de contrato (Polygon, verificadas) ----
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"            # USDC.e (colateral)
CONDITIONAL_TOKENS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"  # CTF (ERC-1155)
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"        # CTF Exchange
NEG_RISK_CTF_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"  # Neg Risk CTF Exchange
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"    # Neg Risk Adapter

# Contratos a los que el EOA de trading aprueba gasto (fase 5).
TRADING_APPROVAL_SPENDERS = (
    CTF_EXCHANGE,
    NEG_RISK_CTF_EXCHANGE,
    NEG_RISK_ADAPTER,
)

# ---- Archivo histórico de pmxt (datos públicos, solo lectura) ----
# Autoindex (listado HTML): https://archive.pmxt.dev/Polymarket/v2/
# Descarga de ficheros (Cloudflare R2):
PMXT_ARCHIVE_DOWNLOAD_BASE = "https://r2v2.pmxt.dev"
# Patrón de fichero: polymarket_orderbook_YYYY-MM-DDTHH.parquet (horario, UTC)
PMXT_ARCHIVE_FILE_TEMPLATE = "polymarket_orderbook_{stamp}.parquet"
# OJO: cada snapshot pesa ~300-400 MB. Descarga solo las horas que necesites.
