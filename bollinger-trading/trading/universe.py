"""Stock universe: 50 stocks across 3 sectors with mapping utilities."""

TECH = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "AVGO", "CRM",
    "ADBE", "AMD", "INTC", "CSCO", "ORCL", "TXN", "QCOM", "IBM", "MU",
]

ENERGY = [
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO",
    "OXY", "HAL", "DVN", "FANG", "HES", "BKR", "KMI", "WMB", "OKE",
]

MINERALS = [
    "NEM", "GOLD", "FNV", "WPM", "AEM", "GFI", "KGC", "AU",
    "RGLD", "AGI", "FCX", "SCCO", "TECK", "BHP", "RIO", "NUE",
]

SECTORS = {
    "Tech": TECH,
    "Energy": ENERGY,
    "Minerals": MINERALS,
}

ALL_SYMBOLS = TECH + ENERGY + MINERALS

# Reverse lookup: symbol -> sector name
SYMBOL_TO_SECTOR = {}
for _sector, _symbols in SECTORS.items():
    for _sym in _symbols:
        SYMBOL_TO_SECTOR[_sym] = _sector

SECTOR_NAMES = list(SECTORS.keys())
