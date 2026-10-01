from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_TCE_DIR = DATA_DIR / "raw" / "tce"
RAW_MANUAL_DIR = DATA_DIR / "raw" / "manual"
METADATA_DIR = DATA_DIR / "metadata"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"

MUNICIPALITY_NAME = "Martinópolis"
TCE_SOURCES: dict[int, str] = {
    year: (
        "https://transparencia.tce.sp.gov.br/sites/default/files/"
        f"conjunto-dados/receitas-{year}.zip"
    )
    for year in range(2021, 2026)
}
