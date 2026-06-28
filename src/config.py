from pathlib import Path

BASE_DIR = Path("data")

DOWNLOAD_DIR = BASE_DIR / "raw" / "downloads"
EXTRACT_DIR = BASE_DIR / "raw" / "extracted"

PARQUET_DIR = BASE_DIR / "processed" / "parquet"
CSV_DIR = BASE_DIR / "processed" / "csv"

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
PARQUET_DIR.mkdir(parents=True, exist_ok=True)
CSV_DIR.mkdir(parents=True, exist_ok=True)

DOSSIER_COMPLET_URLS = {
    2023: "https://www.insee.fr/fr/statistiques/fichier/5359146/dossier_complet_31_12_2023.zip",
    2024: "https://www.insee.fr/fr/statistiques/fichier/5359146/dossier_complet_31_12_2024.zip",
    2025: "https://www.insee.fr/fr/statistiques/fichier/5359146/dossier_complet_31_12_2025.zip",
    2026: "https://www.insee.fr/fr/statistiques/fichier/5359146/dossier_complet.zip",
}